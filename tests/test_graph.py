import os
from datetime import date
from uuid import uuid4

import pytest
from langgraph.types import Command

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "test-langfuse-public-key")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "test-langfuse-secret-key")
os.environ.setdefault("LANGFUSE_BASE_URL", "http://localhost")

from agent import graph
from agent.booking_guardrails import validate_booking_date
from agent.state import (
    BookingConfirmationDecision,
    BookingDetails,
    BookingPhase,
    CustomerDetails,
    TurnIntentDecision,
)

REFERENCE_DATE = date(2026, 5, 5)


class FakeStructuredOutput:
    def __init__(self, outputs, default=None):
        self.outputs = outputs
        self.default = default

    def invoke(self, _prompt):
        if not self.outputs:
            if self.default is not None:
                return self.default
            raise AssertionError("No fake LLM output provided.")

        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


class FakeLLM:
    def __init__(
        self,
        *,
        booking_outputs=(),
        customer_outputs=(),
        confirmation_outputs=(),
        turn_outputs=(),
    ):
        self.outputs_by_schema = {
            BookingDetails: list(booking_outputs),
            CustomerDetails: list(customer_outputs),
            BookingConfirmationDecision: list(confirmation_outputs),
            TurnIntentDecision: list(turn_outputs),
        }
        self.defaults_by_schema = {
            TurnIntentDecision: TurnIntentDecision(intent="phase_input"),
        }

    def with_structured_output(self, schema):
        return FakeStructuredOutput(
            self.outputs_by_schema[schema], self.defaults_by_schema.get(schema)
        )


@pytest.fixture(autouse=True)
def fixed_booking_date(monkeypatch):
    def validate_date_against_reference(value):
        return validate_booking_date(value, REFERENCE_DATE)

    monkeypatch.setattr(graph, "validate_booking_date", validate_date_against_reference)


def graph_config():
    return {"configurable": {"thread_id": f"test-{uuid4()}"}}


def initial_state(message: str):
    return graph.build_initial_state(message)


def interrupt_text(result):
    interrupts = result["__interrupt__"]
    assert len(interrupts) == 1
    return interrupts[0].value


def test_complete_booking_flow_confirms_after_customer_name(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="10-05-2026", time="19:30", party_size=4),
            ],
            customer_outputs=[CustomerDetails(name="Ada Lovelace")],
            confirmation_outputs=[BookingConfirmationDecision(intent="confirm")],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Can I book a table for four on 10-05-2026 at 19:30?"),
        config,
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(Command(resume="Ada Lovelace"), config)
    assert interrupt_text(result) == (
        "Just to confirm, I've got 4 guests "
        "on Sunday, 10 May at 7:30 PM, under the name Ada Lovelace, "
        "is that correct?"
    )

    result = graph.app.invoke(Command(resume="yes"), config)

    assert "__interrupt__" not in result
    assert result["availability"] is True
    assert result["booking_status"] == "confirmed"
    assert result["customer_name"] == "Ada Lovelace"
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time="19:30", party_size=4
    )
    assert result["phase"] == "done"


def test_missing_booking_details_are_requested_and_merged(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(party_size=2),
                BookingDetails(date="11-05-2026", time="18:00"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(initial_state("I'd like a table for two."), config)

    assert interrupt_text(result) == (
        "Sure. "
        "Could you please tell me the day you'd like to come in and what time you'd like?"
    )

    result = graph.app.invoke(Command(resume="11-05-2026 at 18:00"), config)

    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )
    assert result["booking_details"] == BookingDetails(
        date="11-05-2026", time="18:00", party_size=2
    )
    assert result["missing_details"] == []
    assert result["validation_errors"] == []


def test_missing_detail_follow_up_can_change_previously_collected_detail(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="10-05-2026", party_size=2),
                BookingDetails(date="11-05-2026", time="18:00"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("I'd like a table for two on 10-05-2026."), config
    )

    assert (
        interrupt_text(result) == "Sure. Could you please tell me what time you'd like?"
    )
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time=None, party_size=2
    )

    result = graph.app.invoke(
        Command(resume="Actually, make it 11-05-2026 at 18:00."),
        config,
    )

    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )
    assert result["booking_details"] == BookingDetails(
        date="11-05-2026", time="18:00", party_size=2
    )
    assert result["missing_details"] == []
    assert result["validation_errors"] == []


def test_restart_mid_flow_clears_details_and_starts_over(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="10-05-2026", party_size=2),
                BookingDetails(date="11-05-2026", time="19:00", party_size=4),
            ],
            turn_outputs=[
                TurnIntentDecision(intent="phase_input"),
                TurnIntentDecision(intent="restart"),
                TurnIntentDecision(intent="phase_input"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("I'd like a table for two on 10-05-2026."), config
    )

    assert (
        interrupt_text(result) == "Sure. Could you please tell me what time you'd like?"
    )
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time=None, party_size=2
    )

    result = graph.app.invoke(Command(resume="Start over."), config)

    assert interrupt_text(result) == graph.INITIAL_MESSAGE
    assert result["booking_details"] is None
    assert result["customer_name"] is None
    assert result["phase"] == "booking_details"

    result = graph.app.invoke(
        Command(resume="Book 11-05-2026 at 19:00 for four."),
        config,
    )

    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )
    assert result["booking_details"] == BookingDetails(
        date="11-05-2026", time="19:00", party_size=4
    )


def test_invalid_booking_details_are_rejected_before_availability(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="04-05-2026", time="11:59", party_size=11),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Book 04-05-2026 at 11:59 for eleven people."),
        config,
    )

    assert interrupt_text(result) == (
        "Sorry, that date has already passed, "
        "our opening hours are from 12 PM to 10 PM, "
        "and I can book up to 10 guests. "
        "Could you please try again?"
    )
    assert result["availability"] is None
    assert result["booking_details"] == BookingDetails(
        date=None, time=None, party_size=None
    )
    assert [error["field"] for error in result["validation_errors"]] == [
        "date",
        "time",
        "party_size",
    ]


def test_customer_name_retry_keeps_booking_until_name_is_collected(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="12-05-2026", time="20:00", party_size=3),
            ],
            customer_outputs=[
                CustomerDetails(name=None),
                CustomerDetails(name="Grace Hopper"),
            ],
            confirmation_outputs=[BookingConfirmationDecision(intent="confirm")],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Table for three on 12-05-2026 at 20:00."), config
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(Command(resume="It's me."), config)
    assert (
        interrupt_text(result)
        == "Sorry, I didn't catch the name. Can you please repeat it?"
    )
    assert result["booking_details"] == BookingDetails(
        date="12-05-2026", time="20:00", party_size=3
    )

    result = graph.app.invoke(Command(resume="Grace Hopper"), config)
    assert interrupt_text(result) == (
        "Just to confirm, I've got 3 guests "
        "on Tuesday, 12 May at 8 PM, under the name Grace Hopper, "
        "is that correct?"
    )

    result = graph.app.invoke(Command(resume="yes"), config)

    assert "__interrupt__" not in result
    assert result["availability"] is True
    assert result["booking_status"] == "confirmed"
    assert result["customer_name"] == "Grace Hopper"
    assert result["booking_details"] == BookingDetails(
        date="12-05-2026", time="20:00", party_size=3
    )


def test_booking_change_while_waiting_for_name_updates_details(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="12-05-2026", time="20:00", party_size=3),
                BookingDetails(party_size=5),
            ],
            customer_outputs=[
                CustomerDetails(name=None),
                CustomerDetails(name="Grace Hopper"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Table for three on 12-05-2026 at 20:00."), config
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(
        Command(resume="Actually, make that five people."), config
    )

    assert interrupt_text(result) == "Got it. Can I get a name for the reservation?"
    assert result["phase"] == "customer_name"
    assert result["booking_details"] == BookingDetails(
        date="12-05-2026", time="20:00", party_size=5
    )

    result = graph.app.invoke(Command(resume="Grace Hopper"), config)

    assert interrupt_text(result) == (
        "Just to confirm, I've got 5 guests "
        "on Tuesday, 12 May at 8 PM, under the name Grace Hopper, "
        "is that correct?"
    )


def test_confirmation_change_request_updates_booking_before_confirming(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="12-05-2026", time="20:00", party_size=3),
                BookingDetails(date="13-05-2026", time="18:30", party_size=5),
            ],
            customer_outputs=[
                CustomerDetails(name="Grace Hopper"),
                CustomerDetails(name=None),
            ],
            confirmation_outputs=[
                BookingConfirmationDecision(intent="change_request"),
                BookingConfirmationDecision(intent="confirm"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Table for three on 12-05-2026 at 20:00."), config
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(Command(resume="Grace Hopper"), config)
    assert interrupt_text(result) == (
        "Just to confirm, I've got 3 guests "
        "on Tuesday, 12 May at 8 PM, under the name Grace Hopper, "
        "is that correct?"
    )

    result = graph.app.invoke(
        Command(resume="Actually, make it five on 13-05-2026 at 18:30."),
        config,
    )
    assert interrupt_text(result) == (
        "Just to confirm, I've got 5 guests "
        "on Wednesday, 13 May at 6:30 PM, under the name Grace Hopper, "
        "is that correct?"
    )
    assert result["booking_details"] == BookingDetails(
        date="13-05-2026", time="18:30", party_size=5
    )
    assert result["phase"] == "booking_confirmation"

    result = graph.app.invoke(Command(resume="yes"), config)

    assert "__interrupt__" not in result
    assert result["booking_status"] == "confirmed"
    assert result["booking_details"] == BookingDetails(
        date="13-05-2026", time="18:30", party_size=5
    )


def test_confirmation_change_request_can_update_customer_name_only(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="12-05-2026", time="20:00", party_size=3),
                BookingDetails(),
            ],
            customer_outputs=[
                CustomerDetails(name="Grace Hopper"),
                CustomerDetails(name="Ada Lovelace"),
            ],
            confirmation_outputs=[
                BookingConfirmationDecision(intent="change_request"),
                BookingConfirmationDecision(intent="confirm"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Table for three on 12-05-2026 at 20:00."), config
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(Command(resume="Grace Hopper"), config)
    assert interrupt_text(result) == (
        "Just to confirm, I've got 3 guests "
        "on Tuesday, 12 May at 8 PM, under the name Grace Hopper, "
        "is that correct?"
    )

    result = graph.app.invoke(
        Command(resume="Actually, put it under Ada Lovelace."),
        config,
    )

    assert interrupt_text(result) == (
        "Just to confirm, I've got 3 guests "
        "on Tuesday, 12 May at 8 PM, under the name Ada Lovelace, "
        "is that correct?"
    )
    assert result["customer_name"] == "Ada Lovelace"
    assert result["booking_details"] == BookingDetails(
        date="12-05-2026", time="20:00", party_size=3
    )

    result = graph.app.invoke(Command(resume="yes"), config)

    assert "__interrupt__" not in result
    assert result["booking_status"] == "confirmed"
    assert result["customer_name"] == "Ada Lovelace"


def test_invalid_confirmation_change_request_can_be_corrected(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="14-05-2026", time="19:00", party_size=2),
                BookingDetails(time="11:30", party_size=12),
                BookingDetails(time="19:00", party_size=4),
            ],
            customer_outputs=[
                CustomerDetails(name="Ada Lovelace"),
                CustomerDetails(name=None),
                CustomerDetails(name=None),
            ],
            confirmation_outputs=[BookingConfirmationDecision(intent="change_request")],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Book 14-05-2026 at 19:00 for two."), config
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(Command(resume="Ada Lovelace"), config)
    assert interrupt_text(result) == (
        "Just to confirm, I've got 2 guests "
        "on Thursday, 14 May at 7 PM, under the name Ada Lovelace, "
        "is that correct?"
    )

    result = graph.app.invoke(
        Command(resume="Actually, make it 11:30 for 12 people."),
        config,
    )

    assert interrupt_text(result) == (
        "Sorry, our opening hours are from 12 PM to 10 PM "
        "and I can book up to 10 guests. Could you please try again?"
    )
    assert result["phase"] == "change_request"
    assert result["booking_details"] == BookingDetails(
        date="14-05-2026", time=None, party_size=None
    )
    assert [error["field"] for error in result["validation_errors"]] == [
        "time",
        "party_size",
    ]

    result = graph.app.invoke(Command(resume="Okay, make it 19:00 for four."), config)

    assert interrupt_text(result) == (
        "Just to confirm, I've got 4 guests "
        "on Thursday, 14 May at 7 PM, under the name Ada Lovelace, "
        "is that correct?"
    )
    assert result["phase"] == "booking_confirmation"
    assert result["booking_details"] == BookingDetails(
        date="14-05-2026", time="19:00", party_size=4
    )
    assert result["validation_errors"] == []


def test_change_request_can_ask_for_clarification_then_apply_follow_up(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="14-05-2026", time="19:00", party_size=2),
                BookingDetails(),
                BookingDetails(time="17:00"),
            ],
            customer_outputs=[
                CustomerDetails(name="Ada Lovelace"),
                CustomerDetails(name=None),
                CustomerDetails(name=None),
            ],
            confirmation_outputs=[BookingConfirmationDecision(intent="change_request")],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("Book 14-05-2026 at 19:00 for two."), config
    )
    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )

    result = graph.app.invoke(Command(resume="Ada Lovelace"), config)
    assert interrupt_text(result) == (
        "Just to confirm, I've got 2 guests "
        "on Thursday, 14 May at 7 PM, under the name Ada Lovelace, "
        "is that correct?"
    )

    result = graph.app.invoke(Command(resume="Actually, I need to change it."), config)

    assert interrupt_text(result) == "Sure, what would you like to change?"
    assert result["phase"] == "change_request"
    assert result["booking_details"] == BookingDetails(
        date="14-05-2026", time="19:00", party_size=2
    )

    result = graph.app.invoke(Command(resume="Make it 17:00 instead."), config)

    assert interrupt_text(result) == (
        "Just to confirm, I've got 2 guests "
        "on Thursday, 14 May at 5 PM, under the name Ada Lovelace, "
        "is that correct?"
    )
    assert result["phase"] == "booking_confirmation"
    assert result["booking_details"] == BookingDetails(
        date="14-05-2026", time="17:00", party_size=2
    )


def test_out_of_scope_turn_reprompts_without_losing_booking_flow(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="15-05-2026", time="18:00", party_size=2),
            ],
            turn_outputs=[
                TurnIntentDecision(intent="out_of_scope"),
                TurnIntentDecision(intent="phase_input"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(initial_state("What's the weather like?"), config)

    assert interrupt_text(result) == (
        "Sorry, I can only help with table reservations. "
        "Please tell me the date, time, and number of guests for your booking."
    )
    assert result["phase"] == "booking_details"
    assert result["turn_intent"] == "out_of_scope"
    assert result["booking_details"] is None

    result = graph.app.invoke(
        Command(resume="Book 15-05-2026 at 18:00 for two."),
        config,
    )

    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )
    assert result["booking_details"] == BookingDetails(
        date="15-05-2026", time="18:00", party_size=2
    )


def test_out_of_scope_and_unclear_turns_preserve_partial_booking(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="10-05-2026", party_size=2),
                BookingDetails(time="18:00"),
            ],
            turn_outputs=[
                TurnIntentDecision(intent="phase_input"),
                TurnIntentDecision(intent="out_of_scope"),
                TurnIntentDecision(intent="unclear"),
                TurnIntentDecision(intent="phase_input"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(
        initial_state("I'd like a table for two on 10-05-2026."), config
    )
    assert (
        interrupt_text(result) == "Sure. Could you please tell me what time you'd like?"
    )
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time=None, party_size=2
    )

    result = graph.app.invoke(Command(resume="What's the weather?"), config)
    assert interrupt_text(result) == (
        "Sorry, I can only help with table reservations. "
        "Please tell me the date, time, and number of guests for your booking."
    )
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time=None, party_size=2
    )

    result = graph.app.invoke(Command(resume="hmm, wait, no, maybe"), config)
    assert interrupt_text(result) == (
        "Sorry, I didn't understand that. Can you please rephrase?"
    )
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time=None, party_size=2
    )

    result = graph.app.invoke(Command(resume="18:00."), config)

    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )
    assert result["booking_details"] == BookingDetails(
        date="10-05-2026", time="18:00", party_size=2
    )


def test_unclear_turn_uses_fallback_and_allows_recovery(monkeypatch):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(
            booking_outputs=[
                BookingDetails(date="16-05-2026", time="20:00", party_size=4),
            ],
            turn_outputs=[
                TurnIntentDecision(intent="unclear"),
                TurnIntentDecision(intent="phase_input"),
            ],
        ),
    )
    config = graph_config()

    result = graph.app.invoke(initial_state("mumble mumble"), config)

    assert interrupt_text(result) == (
        "Sorry, I didn't understand that. Can you please rephrase?"
    )
    assert result["phase"] == "booking_details"
    assert result["turn_intent"] == "unclear"
    assert result["booking_details"] is None

    result = graph.app.invoke(
        Command(resume="Book 16-05-2026 at 20:00 for four."),
        config,
    )

    assert (
        interrupt_text(result)
        == "Great, that time is available. Can I get a name for the reservation?"
    )
    assert result["booking_details"] == BookingDetails(
        date="16-05-2026", time="20:00", party_size=4
    )


@pytest.mark.parametrize(
    ("phase", "expected_reply"),
    [
        (
            BookingPhase.BOOKING_DETAILS,
            "I can help you book a table at Le Jardin. "
            "Just tell me the date and time you'd like to come in, "
            "and how many people are in your party.",
        ),
        (
            BookingPhase.CUSTOMER_NAME,
            "Please tell me the name to put on the reservation.",
        ),
        (
            BookingPhase.CONFIRMATION,
            "Please say 'yes' to book it, 'no' to cancel it, "
            "or tell me what you'd like to change.",
        ),
        (
            BookingPhase.CHANGE_REQUEST,
            "Please tell me what you'd like to change about your booking.",
        ),
    ],
)
def test_help_preserves_state_from_each_active_phase(
    monkeypatch, phase, expected_reply
):
    booking_details = BookingDetails(date="12-05-2026", time="20:00", party_size=3)
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(turn_outputs=[TurnIntentDecision(intent="help")]),
    )
    config = graph_config()
    state = initial_state("help")
    state.update(
        {
            "booking_details": booking_details,
            "customer_name": "Grace Hopper",
            "phase": phase,
        }
    )

    result = graph.app.invoke(state, config)

    assert interrupt_text(result) == expected_reply
    assert result["phase"] == phase
    assert result["booking_details"] == booking_details
    assert result["customer_name"] == "Grace Hopper"


@pytest.mark.parametrize(
    "phase",
    [
        BookingPhase.BOOKING_DETAILS,
        BookingPhase.CUSTOMER_NAME,
        BookingPhase.CONFIRMATION,
        BookingPhase.CHANGE_REQUEST,
    ],
)
def test_cancel_ends_from_each_active_phase(monkeypatch, phase):
    monkeypatch.setattr(
        graph,
        "llm",
        FakeLLM(turn_outputs=[TurnIntentDecision(intent="cancel")]),
    )
    config = graph_config()
    state = initial_state("cancel")
    state.update(
        {
            "booking_details": BookingDetails(
                date="12-05-2026", time="20:00", party_size=3
            ),
            "customer_name": "Grace Hopper",
            "phase": phase,
        }
    )

    result = graph.app.invoke(state, config)

    assert "__interrupt__" not in result
    assert result["booking_status"] == "cancelled"
    assert result["phase"] == "done"
