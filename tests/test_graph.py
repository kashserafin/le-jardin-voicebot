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
from agent.state import BookingConfirmationDecision, BookingDetails, CustomerDetails


REFERENCE_DATE = date(2026, 5, 5)


class FakeStructuredOutput:
    def __init__(self, outputs):
        self.outputs = outputs

    def invoke(self, _prompt):
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


class FakeLLM:
    def __init__(self, *, booking_outputs=(), customer_outputs=(), confirmation_outputs=()):
        self.outputs_by_schema = {
            BookingDetails: list(booking_outputs),
            CustomerDetails: list(customer_outputs),
            BookingConfirmationDecision: list(confirmation_outputs),
        }

    def with_structured_output(self, schema):
        return FakeStructuredOutput(self.outputs_by_schema[schema])


@pytest.fixture(autouse=True)
def fixed_booking_date(monkeypatch):
    def validate_date_against_reference(value):
        return validate_booking_date(value, REFERENCE_DATE)

    monkeypatch.setattr(graph, "validate_booking_date", validate_date_against_reference)


def graph_config():
    return {"configurable": {"thread_id": f"test-{uuid4()}"}}


def initial_state(message: str):
    return {
        "last_message": message,
        "booking_details": None,
        "availability": None,
        "customer_name": None,
        "missing_details": None,
        "validation_errors": None,
        "booking_status": None,
    }


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
    assert interrupt_text(result) == "Great, that time is available. Can I get a name for the reservation?"

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
    assert result["booking_details"] == BookingDetails(date="10-05-2026", time="19:30", party_size=4)


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

    assert interrupt_text(result) == "Great, that time is available. Can I get a name for the reservation?"
    assert result["booking_details"] == BookingDetails(date="11-05-2026", time="18:00", party_size=2)
    assert result["missing_details"] == []
    assert result["validation_errors"] == []


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
    assert result["booking_details"] == BookingDetails(date=None, time=None, party_size=None)
    assert [error["field"] for error in result["validation_errors"]] == ["date", "time", "party_size"]


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

    result = graph.app.invoke(initial_state("Table for three on 12-05-2026 at 20:00."), config)
    assert interrupt_text(result) == "Great, that time is available. Can I get a name for the reservation?"

    result = graph.app.invoke(Command(resume="It's me."), config)
    assert interrupt_text(result) == "Sorry, I didn't catch the name. Can you please repeat it?"
    assert result["booking_details"] == BookingDetails(date="12-05-2026", time="20:00", party_size=3)

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
    assert result["booking_details"] == BookingDetails(date="12-05-2026", time="20:00", party_size=3)
