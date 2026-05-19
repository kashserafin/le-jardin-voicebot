import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent.booking_guardrails import (
    booking_rules_summary,
    validate_booking_date,
    validate_booking_time,
    validate_party_size,
    BookingValidationError,
)
from agent.helpers import (
    build_missing_details_question,
    build_booking_confirmation_question,
    build_help_message,
)
from agent.state import (
    BookingAgentState,
    BookingConfirmationDecision,
    BookingConfirmationIntent,
    BookingDetails,
    BookingPhase,
    BookingStatus,
    BookingValidationIssue,
    CustomerDetails,
    TurnIntent,
    TurnIntentDecision,
)
from agent.prompts import (
    BOOKING_DETAILS_PROMPT,
    CUSTOMER_NAME_PROMPT,
    BOOKING_CONFIRMATION_PROMPT,
    TURN_INTENT_PROMPT,
)
from openai_client import OpenAIClient

INITIAL_MESSAGE = "Welcome to Le Jardin! I can help you book a table. What day would you like to come in?"
OUT_OF_SCOPE_MESSAGE = "Sorry, I can only help with table reservations. Please tell me the date, time, and number of guests for your booking."
GET_CUSTOMER_NAME_MESSAGE = (
    "Great, that time is available. Can I get a name for the reservation?"
)
RETRY_CUSTOMER_NAME_MESSAGE = (
    "Sorry, I didn't catch the name. Can you please repeat it?"
)
RETRY_CONFIRMATION_MESSAGE = (
    "Sorry, I didn't catch that. Should I book this table as described?"
)
CHANGE_REQUEST_MESSAGE = "Sure, what would you like to change?"
FALLBACK_MESSAGE = "Sorry, I didn't understand that. Can you please rephrase?"

openai_client = OpenAIClient()
llm = openai_client.chat_model(model="gpt-5.4-mini")
logger = logging.getLogger(__name__)


def build_initial_state(message: str) -> BookingAgentState:
    return {
        "last_message": message,
        "booking_details": None,
        "availability": None,
        "customer_name": None,
        "missing_details": None,
        "validation_errors": None,
        "booking_status": None,
        "phase": BookingPhase.BOOKING_DETAILS,
        "turn_intent": TurnIntent.PHASE_INPUT,
        "reply_text": None,
    }


# Define node functions
def route_turn(state: BookingAgentState) -> Command:
    if state.get("booking_status") in ["confirmed", "cancelled"]:
        return Command(goto=END)

    turn_intent = classify_turn_intent(state)
    match turn_intent:
        case TurnIntent.RESTART:
            return Command(update={"turn_intent": turn_intent}, goto="restart")
        case TurnIntent.CANCEL | TurnIntent.HELP:
            return Command(update={"turn_intent": turn_intent}, goto="global_action")
        case TurnIntent.OUT_OF_SCOPE:
            return Command(
                update={
                    "turn_intent": turn_intent,
                    "reply_text": OUT_OF_SCOPE_MESSAGE,
                },
                goto="ask_user",
            )
        case TurnIntent.UNCLEAR:
            return Command(update={"turn_intent": turn_intent}, goto="ask_user")
        case _:
            return Command(
                update={
                    "phase": state.get("phase", BookingPhase.BOOKING_DETAILS),
                    "turn_intent": TurnIntent.PHASE_INPUT,
                },
                goto="advance",
            )


def advance(state: BookingAgentState) -> Command:
    phase = state.get("phase", BookingPhase.BOOKING_DETAILS)

    match phase:
        case BookingPhase.BOOKING_DETAILS:
            return advance_booking_details(state)
        case BookingPhase.CUSTOMER_NAME:
            return advance_customer_name(state)
        case BookingPhase.CONFIRMATION:
            return advance_booking_confirmation(state)
        case BookingPhase.CHANGE_REQUEST:
            return advance_change_request(state)
        case BookingPhase.DONE:
            return Command(goto=END)
        case _:
            return Command(goto="fallback")


def advance_booking_details(state: BookingAgentState) -> Command:
    booking_details = extract_booking_details(state)
    validated_details, missing_fields, validation_errors = (
        validate_booking_details_model(booking_details)
    )

    if missing_fields or validation_errors:
        missing_details_question = build_missing_details_question(
            missing_fields, validation_errors
        )
        return Command(
            update={
                "booking_details": validated_details,
                "availability": None,
                "missing_details": missing_fields,
                "validation_errors": validation_errors,
                "phase": BookingPhase.BOOKING_DETAILS,
                "reply_text": missing_details_question,
            },
            goto="ask_user",
        )

    customer_name = state.get("customer_name")
    if customer_name:
        confirmation_question = build_booking_confirmation_question(
            validated_details, customer_name
        )
        return Command(
            update={
                "booking_details": validated_details,
                "availability": True,
                "missing_details": [],
                "validation_errors": [],
                "phase": BookingPhase.CONFIRMATION,
                "reply_text": confirmation_question,
            },
            goto="ask_user",
        )

    return Command(
        update={
            "booking_details": validated_details,
            "availability": True,
            "missing_details": [],
            "validation_errors": [],
            "phase": BookingPhase.CUSTOMER_NAME,
            "reply_text": GET_CUSTOMER_NAME_MESSAGE,
        },
        goto="ask_user",
    )


def advance_customer_name(state: BookingAgentState) -> Command:
    customer_name = extract_customer_name(state.get("last_message"))

    # If we couldn't extract a name from the user's message, ask them to provide it again
    if not customer_name:
        return Command(
            update={
                "phase": BookingPhase.CUSTOMER_NAME,
                "reply_text": RETRY_CUSTOMER_NAME_MESSAGE,
            },
            goto="ask_user",
        )

    # If we were able to extract the name, ask the user to confirm the booking details along with their name
    booking_details = state.get("booking_details")
    return Command(
        update={
            "customer_name": customer_name,
            "phase": BookingPhase.CONFIRMATION,
            "reply_text": build_booking_confirmation_question(
                booking_details, customer_name
            ),
        },
        goto="ask_user",
    )


def advance_booking_confirmation(state: BookingAgentState) -> Command:
    decision = classify_booking_confirmation(state.get("last_message"))

    match decision:
        case BookingConfirmationIntent.CONFIRM:
            return Command(
                update={
                    "booking_status": BookingStatus.CONFIRMED,
                    "phase": BookingPhase.DONE,
                    "reply_text": None,
                },
                goto=END,
            )
        case BookingConfirmationIntent.DECLINE:
            return Command(
                update={
                    "booking_status": BookingStatus.CANCELLED,
                    "phase": BookingPhase.DONE,
                    "reply_text": None,
                },
                goto=END,
            )
        case BookingConfirmationIntent.CHANGE_REQUEST:
            return advance_change_request(state)
        case _:
            return Command(
                update={
                    "phase": BookingPhase.CONFIRMATION,
                    "reply_text": RETRY_CONFIRMATION_MESSAGE,
                },
                goto="ask_user",
            )


def advance_change_request(state: BookingAgentState) -> Command:
    current_details = state.get("booking_details") or BookingDetails()
    current_name = state.get("customer_name")
    changed_details = extract_booking_details(state, current_details)
    changed_name = extract_customer_name(state.get("last_message"))

    details_changed = changed_details != current_details
    name_changed = bool(changed_name and changed_name != current_name)

    # If the user requested a change but we couldn't extract any changes from their message, ask them to clarify
    if not details_changed and not name_changed:
        return Command(
            update={
                "phase": BookingPhase.CHANGE_REQUEST,
                "reply_text": CHANGE_REQUEST_MESSAGE,
            },
            goto="ask_user",
        )

    # If we were able to extract changes, validate the new details and ask for any missing or invalid information
    validated_details, missing_fields, validation_errors = (
        validate_booking_details_model(changed_details)
    )
    customer_name = changed_name or current_name

    if missing_fields or validation_errors:
        question = build_missing_details_question(missing_fields, validation_errors)
        return Command(
            update={
                "booking_details": validated_details,
                "availability": None,
                "customer_name": customer_name,
                "missing_details": missing_fields,
                "validation_errors": validation_errors,
                "phase": BookingPhase.CHANGE_REQUEST,
                "reply_text": question,
            },
            goto="ask_user",
        )

    # If the new details are valid but we don't have a customer name yet, ask for the name
    if not customer_name:
        return Command(
            update={
                "booking_details": validated_details,
                "availability": True,
                "missing_details": [],
                "validation_errors": [],
                "phase": BookingPhase.CUSTOMER_NAME,
                "reply_text": GET_CUSTOMER_NAME_MESSAGE,
            },
            goto="ask_user",
        )

    # If the new details are valid and we have a customer name, ask the user to confirm the updated booking details
    return Command(
        update={
            "booking_details": validated_details,
            "availability": True,
            "customer_name": customer_name,
            "missing_details": [],
            "validation_errors": [],
            "phase": BookingPhase.CONFIRMATION,
            "reply_text": build_booking_confirmation_question(
                validated_details, customer_name
            ),
        },
        goto="ask_user",
    )


def restart(state: BookingAgentState) -> Command:
    return Command(update=build_initial_state(INITIAL_MESSAGE), goto="ask_user")


def global_action(state: BookingAgentState) -> Command:
    turn_intent = state.get("turn_intent")
    match turn_intent:
        case TurnIntent.CANCEL:
            return Command(
                update={
                    "booking_status": BookingStatus.CANCELLED,
                    "phase": BookingPhase.DONE,
                    "reply_text": None,
                },
                goto=END,
            )
        case TurnIntent.HELP:
            phase = state.get("phase", BookingPhase.BOOKING_DETAILS)
            return Command(
                update={"phase": phase, "reply_text": build_help_message(phase)},
                goto="ask_user",
            )
        case _:
            return Command(goto="fallback")


def fallback(state: BookingAgentState) -> Command:
    return Command(
        update={
            "phase": state.get("phase", BookingPhase.BOOKING_DETAILS),
            "reply_text": FALLBACK_MESSAGE,
        },
        goto="ask_user",
    )


def ask_user(state: BookingAgentState) -> Command:
    reply_text = state.get("reply_text")
    user_input = interrupt(reply_text)

    return Command(
        update={"last_message": user_input, "reply_text": None}, goto="route_turn"
    )


# Helper functions to classify user intent and extract structured information from user messages
def classify_turn_intent(state: BookingAgentState) -> TurnIntent:
    structured_llm = llm.with_structured_output(TurnIntentDecision)

    try:
        decision = structured_llm.invoke(
            TURN_INTENT_PROMPT.format(
                phase=state.get("phase", BookingPhase.BOOKING_DETAILS),
                last_message=state.get("last_message"),
            )
        )
    except Exception as e:
        logger.error(f"Error classifying turn intent: {str(e)}")
        decision = TurnIntentDecision(intent=TurnIntent.UNCLEAR)

        return decision.intent


def classify_booking_confirmation(
    last_message: str | None,
) -> BookingConfirmationIntent:
    structured_llm = llm.with_structured_output(BookingConfirmationDecision)

    try:
        decision = structured_llm.invoke(
            BOOKING_CONFIRMATION_PROMPT.format(
                booking_rules=booking_rules_summary(),
                last_message=last_message,
            )
        )
    except Exception as e:
        logger.error(f"Error classifying booking confirmation decision: {str(e)}")
        decision = BookingConfirmationDecision(intent=BookingConfirmationIntent.UNCLEAR)

    return decision.intent


def extract_booking_details(
    state: BookingAgentState, current_details: BookingDetails | None = None
) -> BookingDetails:
    structured_llm = llm.with_structured_output(BookingDetails)
    current_details = (
        current_details or state.get("booking_details") or BookingDetails()
    )

    try:
        new_details = structured_llm.invoke(
            BOOKING_DETAILS_PROMPT.format(
                booking_rules=booking_rules_summary(),
                last_message=state.get("last_message"),
            )
        )
    except Exception as e:
        logger.error(f"Error extracting booking details: {str(e)}")
        new_details = None

    booking_details = BookingDetails(
        date=(
            new_details.date
            if new_details is not None and new_details.date is not None
            else current_details.date
        ),
        time=(
            new_details.time
            if new_details is not None and new_details.time is not None
            else current_details.time
        ),
        party_size=(
            new_details.party_size
            if new_details is not None and new_details.party_size is not None
            else current_details.party_size
        ),
    )

    return booking_details


def extract_customer_name(last_message: str | None) -> str | None:
    structured_llm = llm.with_structured_output(CustomerDetails)

    try:
        customer_details = structured_llm.invoke(
            CUSTOMER_NAME_PROMPT.format(last_message=last_message)
        )
    except Exception as e:
        logger.error(f"Error extracting customer name: {str(e)}")
        return None

    return customer_details.name if customer_details is not None else None


def validate_booking_details_model(
    booking_details: BookingDetails | None,
) -> tuple[BookingDetails, list[str], list[BookingValidationIssue]]:
    booking_details = booking_details or BookingDetails()
    missing_fields = []
    validation_errors = []
    date = None
    time = None
    party_size = None

    if booking_details.date is None:
        missing_fields.append("date")
    else:
        try:
            date = validate_booking_date(booking_details.date)
        except BookingValidationError as error:
            validation_errors.append(
                create_booking_validation_issue(
                    error, booking_details.date, "25-12-2024"
                )
            )

    if booking_details.time is None:
        missing_fields.append("time")
    else:
        try:
            time = validate_booking_time(booking_details.time)
        except BookingValidationError as error:
            validation_errors.append(
                create_booking_validation_issue(error, booking_details.time, "19:30")
            )

    if booking_details.party_size is None:
        missing_fields.append("party_size")
    else:
        try:
            party_size = validate_party_size(booking_details.party_size)
        except BookingValidationError as error:
            validation_errors.append(
                create_booking_validation_issue(error, booking_details.party_size, "4")
            )

    return (
        BookingDetails(date=date, time=time, party_size=party_size),
        missing_fields,
        validation_errors,
    )


def create_booking_validation_issue(
    error: BookingValidationError,
    value: str | int,
    example: str,
) -> BookingValidationIssue:
    return {
        "field": error.field,
        "value": str(value),
        "message": error.message,
        "reason": error.reason,
        "example": example,
    }


# Create the graph
workflow = StateGraph(BookingAgentState)

# Add nodes
workflow.add_node("route_turn", route_turn)
workflow.add_node("advance", advance)
workflow.add_node("restart", restart)
workflow.add_node("global_action", global_action)
workflow.add_node("fallback", fallback)
workflow.add_node("ask_user", ask_user)

# Add edges
workflow.add_edge(START, "route_turn")

# Compile the graph with a memory checkpointer to persist state across turns
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
