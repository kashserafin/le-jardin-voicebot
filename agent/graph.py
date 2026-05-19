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
                goto="fallback",
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
    customer_name = extract_cutomer_name(state.get("last_message"))

    if not customer_name:
        return Command(
            update={
                "phase": BookingPhase.CUSTOMER_NAME,
                "reply_text": RETRY_CUSTOMER_NAME_MESSAGE,
            },
            goto="ask_user",
        )

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
    return {}


def restart(state: BookingAgentState) -> Command:
    return Command(update=build_initial_state(INITIAL_MESSAGE), goto="ask_user")


# TODO: Implement global_action function to handle global commands like cancel and help, and fallback function to handle out-of-scope and unclear input
def global_action(state: BookingAgentState) -> Command:
    return {}


def fallback(state: BookingAgentState) -> Command:
    return {}


# TODO: Implement ask user function to interrupt the normal flow and ask the user for input when needed
def ask_user(state: BookingAgentState) -> Command:
    return {}


# Helper functions to classify user intent and extract structured information from user messages
def classify_turn_intent(state: BookingAgentState) -> TurnIntent:
    structured_llm = llm.with_structured_output(TurnIntentDecision)

    try:
        decision = structured_llm.invoke(
            TURN_INTENT_PROMPT.format(
                state.get("phase", "booking_details"),
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


def extract_cutomer_name(last_message: str | None) -> str | None:
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


# # Define node functions
# def collect_booking_details(
# 	state: BookingAgentState,
# ) -> Command[Literal["validate_booking_details"]]:

#     structured_llm = llm.with_structured_output(BookingDetails)

#     current_bd = state.get("booking_details") or BookingDetails()

#     try:
#         new_bd = structured_llm.invoke(BOOKING_DETAILS_PROMPT.format(booking_rules=booking_rules_summary(), last_message=state["last_message"]))

#         merged_bd = BookingDetails(
#             date=new_bd.date if new_bd is not None and new_bd.date is not None else current_bd.date,
#             time=new_bd.time if new_bd is not None and new_bd.time is not None else current_bd.time,
#             party_size=new_bd.party_size if new_bd is not None and new_bd.party_size is not None else current_bd.party_size
#         )
#     except Exception as e:
#         print(f"Error parsing booking details: {str(e)}")
#         merged_bd = current_bd

#     return Command(update={"booking_details":merged_bd}, goto="validate_booking_details")


# def validate_booking_details(
# 	state: BookingAgentState,
# ) -> Command[Literal["check_availability", "ask_for_missing_details"]]:

#     missing_fields = []
#     validation_errors = []

#     bd = state.get("booking_details")
#     date_value = bd.date
#     time_value = bd.time
#     party_size_value = bd.party_size
#     date, time, party_size = None, None, None

#     if date_value is None:
#         missing_fields.append("date")
#     else:
#         try:
#             date = validate_booking_date(date_value)
#         except BookingValidationError as error:
#             validation_errors.append({"field": error.field, "value": date_value, "message": error.message, "reason": error.reason, "example": "25-12-2024"})

#     if time_value is None:
#         missing_fields.append("time")
#     else:
#         try:
#             time = validate_booking_time(time_value)
#         except BookingValidationError as error:
#             validation_errors.append({"field": error.field, "value": time_value, "message": error.message, "reason": error.reason, "example": "19:30"})

#     if party_size_value is None:
#         missing_fields.append("party_size")
#     else:
#         try:
#             party_size = validate_party_size(party_size_value)
#         except BookingValidationError as error:
#             validation_errors.append({"field": error.field, "value": party_size_value, "message": error.message, "reason": error.reason, "example": "4"})

#     validated_bd = BookingDetails(date=date, time=time, party_size=party_size)
#     goto = "check_availability" if not missing_fields and not validation_errors else "ask_for_missing_details"

#     return Command(update={"booking_details": validated_bd, "missing_details": missing_fields, "validation_errors": validation_errors}, goto=goto)


# def ask_for_missing_details(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_booking_details"]]:

#     missing_fields = state.get("missing_details", [])
#     validation_errors = state.get("validation_errors", [])

#     question = build_missing_details_question(missing_fields, validation_errors)
#     if not question:
#         question = "Sorry, I missed that. What day and time would you like to book, and for how many people?"

#     # Interrupt the normal flow to ask the user for missing/invalid details
#     user_input = interrupt(question)

#     return Command(update={"last_message": user_input,}, goto="collect_booking_details")


# # This node always returns True for availability for demo purposes, but in a real implementation this would check against the restaurant's booking system
# def check_availability(
# 	state: BookingAgentState,
# ) -> Command[Literal["ask_for_customer_name"]]:
#     return Command(update={"availability": True}, goto="ask_for_customer_name")


# def ask_for_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_customer_name"]]:

#     # Interrupt the normal flow to ask the user for their name
#     user_input = interrupt("Great, that time is available. Can I get a name for the reservation?")

#     return Command(update={"last_message": user_input}, goto="collect_customer_name")


# def retry_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_customer_name"]]:

#     # Interrupt the normal flow to ask the user for their name again if it was not captured successfully the first time
#     user_input = interrupt("Sorry, I didn't catch the name. Can you please repeat it?")

#     return Command(update={"last_message": user_input}, goto="collect_customer_name")


# def collect_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["confirm_booking", "retry_customer_name"]]:

#     structured_llm = llm.with_structured_output(CustomerDetails)

#     try:
#         customer_details = structured_llm.invoke(CUSTOMER_NAME_PROMPT.format(last_message=state["last_message"]))
#         customer_name = customer_details.name if customer_details is not None else None
#     except Exception as e:
#         print(f"Error parsing customer name: {e}")
#         customer_name = None

#     if not customer_name:
#         return Command(goto="retry_customer_name")

#     return Command(update={"customer_name": customer_name}, goto="confirm_booking")


# def confirm_booking(
#     state: BookingAgentState
# ) -> Command[Literal["classify_booking_confirmation"]]:

#     bd = state.get("booking_details")
#     customer_name = state.get("customer_name")

#     question = build_booking_confirmation_question(bd, customer_name)

#     # Interrupt the normal flow to ask the user to confirm the booking details before finalizing the booking
#     user_input = interrupt(question)

#     return Command(update={"last_message": user_input}, goto="classify_booking_confirmation")


# def classify_booking_confirmation(
#     state: BookingAgentState
# ) -> Command[Literal["finalize_booking", "cancel_booking"]]:

#     structured_llm = llm.with_structured_output(BookingConfirmationDecision)

#     try:
#         decision = structured_llm.invoke(
#             BOOKING_CONFIRMATION_PROMPT.format(
#                 booking_rules=booking_rules_summary(),
#                 last_message=state["last_message"]
#             )
#         )
#     except Exception as e:
#         print(f"Error parsing booking confirmation decision: {e}")
#         decision = BookingConfirmationDecision(intent="unclear")

#     if decision is None:
#         decision = BookingConfirmationDecision(intent="unclear")

#     match decision.intent:
#         case "confirm":
#             return Command(goto="finalize_booking")
#         case "decline":
#             return Command(goto="cancel_booking")
#         case "change_request":
#             # TODO: Implement logic to handle change requests
#             print("Change request received, cant handle it yet")
#         case _:
#             # TODO: Handle unclear intent by asking the user for clarification
#             print(f"Unhandled booking confirmation intent: {decision.intent}")

#     return {}


# def finalize_booking(state: BookingAgentState):
#     # In a real implementation, this node would create the booking in the restaurant's booking system
#     return Command(update={"booking_status": "confirmed"})


# def cancel_booking(state: BookingAgentState):
#     return Command(update={"booking_status": "cancelled"})


# # Create the graph
# workflow = StateGraph(BookingAgentState)

# # Add nodes
# workflow.add_node("collect_booking_details", collect_booking_details)
# workflow.add_node("validate_booking_details", validate_booking_details)
# workflow.add_node("check_availability", check_availability)
# workflow.add_node("ask_for_missing_details", ask_for_missing_details)
# workflow.add_node("ask_for_customer_name", ask_for_customer_name)
# workflow.add_node("retry_customer_name", retry_customer_name)
# workflow.add_node("collect_customer_name", collect_customer_name)
# workflow.add_node("confirm_booking", confirm_booking)
# workflow.add_node("classify_booking_confirmation", classify_booking_confirmation)
# workflow.add_node("finalize_booking", finalize_booking)
# workflow.add_node("cancel_booking", cancel_booking)

# # Add edges
# workflow.add_edge(START, "collect_booking_details")
# workflow.add_edge("finalize_booking", END)
# workflow.add_edge("cancel_booking", END)

# memory = MemorySaver()
# app = workflow.compile(checkpointer=memory)
