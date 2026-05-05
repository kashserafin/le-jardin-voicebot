from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent.booking_guardrails import booking_rules_summary, validate_booking_date, validate_booking_time, validate_party_size, BookingValidationError
from agent.helpers import build_missing_details_question, build_booking_confirmation_question
from agent.state import BookingAgentState, BookingConfirmationDecision, BookingDetails, CustomerDetails
from agent.prompts import BOOKING_DETAILS_PROMPT, CUSTOMER_NAME_PROMPT, BOOKING_CONFIRMATION_PROMPT
from openai_client import OpenAIClient


INITIAL_MESSAGE = "Welcome to Le Jardin! I can help you book a table. What day would you like to come in?"

openai_client = OpenAIClient()
llm = openai_client.chat_model(model="gpt-5.4-mini")


# Define node functions
def collect_booking_details(
	state: BookingAgentState,
) -> Command[Literal["validate_booking_details"]]:

    structured_llm = llm.with_structured_output(BookingDetails)

    current_bd = state.get("booking_details") or BookingDetails()

    try:
        new_bd = structured_llm.invoke(BOOKING_DETAILS_PROMPT.format(booking_rules=booking_rules_summary(), last_message=state["last_message"]))

        merged_bd = BookingDetails(
            date=new_bd.date if new_bd is not None and new_bd.date is not None else current_bd.date,
            time=new_bd.time if new_bd is not None and new_bd.time is not None else current_bd.time,
            party_size=new_bd.party_size if new_bd is not None and new_bd.party_size is not None else current_bd.party_size
        )
    except Exception as e:
        print(f"Error parsing booking details: {str(e)}")
        merged_bd = current_bd

    return Command(update={"booking_details":merged_bd}, goto="validate_booking_details")


def validate_booking_details(
	state: BookingAgentState,
) -> Command[Literal["check_availability", "ask_for_missing_details"]]:
    
    missing_fields = []
    validation_errors = []

    bd = state.get("booking_details")
    date_value = bd.date
    time_value = bd.time
    party_size_value = bd.party_size
    date, time, party_size = None, None, None

    if date_value is None:
        missing_fields.append("date")
    else:
        try:
            date = validate_booking_date(date_value)
        except BookingValidationError as error:
            validation_errors.append({"field": error.field, "value": date_value, "message": error.message, "reason": error.reason, "example": "25-12-2024"})

    if time_value is None:
        missing_fields.append("time")
    else:
        try:
            time = validate_booking_time(time_value)
        except BookingValidationError as error:
            validation_errors.append({"field": error.field, "value": time_value, "message": error.message, "reason": error.reason, "example": "19:30"})

    if party_size_value is None:
        missing_fields.append("party_size")
    else:
        try:
            party_size = validate_party_size(party_size_value)
        except BookingValidationError as error:
            validation_errors.append({"field": error.field, "value": party_size_value, "message": error.message, "reason": error.reason, "example": "4"})

    validated_bd = BookingDetails(date=date, time=time, party_size=party_size)
    goto = "check_availability" if not missing_fields and not validation_errors else "ask_for_missing_details"

    return Command(update={"booking_details": validated_bd, "missing_details": missing_fields, "validation_errors": validation_errors}, goto=goto)


def ask_for_missing_details(
	state: BookingAgentState,
) -> Command[Literal["collect_booking_details"]]:
    
    missing_fields = state.get("missing_details", [])
    validation_errors = state.get("validation_errors", [])

    question = build_missing_details_question(missing_fields, validation_errors)
    if not question:
        question = "Sorry, I missed that. What day and time would you like to book, and for how many people?"

    # Interrupt the normal flow to ask the user for missing/invalid details
    user_input = interrupt(question)

    return Command(update={"last_message": user_input,}, goto="collect_booking_details")


# This node always returns True for availability for demo purposes, but in a real implementation this would check against the restaurant's booking system
def check_availability(
	state: BookingAgentState,
) -> Command[Literal["ask_for_customer_name"]]:
    return Command(update={"availability": True}, goto="ask_for_customer_name")


def ask_for_customer_name(
	state: BookingAgentState,
) -> Command[Literal["collect_customer_name"]]:

    # Interrupt the normal flow to ask the user for their name
    user_input = interrupt("Great, that time is available. Can I get a name for the reservation?")

    return Command(update={"last_message": user_input}, goto="collect_customer_name")


def retry_customer_name(
	state: BookingAgentState,
) -> Command[Literal["collect_customer_name"]]:

    # Interrupt the normal flow to ask the user for their name again if it was not captured successfully the first time
    user_input = interrupt("SSorry, I didn't catch the name. Can you please repeat it?")

    return Command(update={"last_message": user_input}, goto="collect_customer_name")


def collect_customer_name(
	state: BookingAgentState,
) -> Command[Literal["confirm_booking", "retry_customer_name"]]:

    structured_llm = llm.with_structured_output(CustomerDetails)

    try:
        customer_details = structured_llm.invoke(CUSTOMER_NAME_PROMPT.format(last_message=state["last_message"]))
        customer_name = customer_details.name if customer_details is not None else None
    except Exception as e:
        print(f"Error parsing customer name: {e}")
        customer_name = None

    if not customer_name:
        return Command(goto="retry_customer_name")

    return Command(update={"customer_name": customer_name}, goto="confirm_booking")


def confirm_booking(
    state: BookingAgentState
) -> Command[Literal["classify_booking_confirmation"]]:
    
    bd = state.get("booking_details")
    customer_name = state.get("customer_name")

    question = build_booking_confirmation_question(bd, customer_name)

    # Interrupt the normal flow to ask the user to confirm the booking details before finalizing the booking
    user_input = interrupt(question)

    return Command(update={"last_message": user_input}, goto="classify_booking_confirmation")


def classify_booking_confirmation(
    state: BookingAgentState
) -> Command[Literal["finalize_booking", "cancel_booking"]]:
    
    structured_llm = llm.with_structured_output(BookingConfirmationDecision)
    
    try:
        decision = structured_llm.invoke(
            BOOKING_CONFIRMATION_PROMPT.format(
                booking_rules=booking_rules_summary(),
                last_message=state["last_message"]
            )
        )
    except Exception as e:
        print(f"Error parsing booking confirmation decision: {e}")
        decision = BookingConfirmationDecision(intent="unclear")
    
    if decision is None:
        decision = BookingConfirmationDecision(intent="unclear")
    
    match decision.intent:
        case "confirm":
            return Command(goto="finalize_booking")
        case "decline":
            return Command(goto="cancel_booking")
        case "change_request":
            # TODO: Implement logic to handle change requests
            print("Change request received, cant handle it yet")
        case _:
            # TODO: Handle unclear intent by asking the user for clarification
            print(f"Unhandled booking confirmation intent: {decision.intent}")

    return {}


def finalize_booking(state: BookingAgentState):
    # In a real implementation, this node would create the booking in the restaurant's booking system
    return Command(update={"booking_status": "confirmed"})


def cancel_booking(state: BookingAgentState):
    return Command(update={"booking_status": "cancelled"})


# Create the graph
workflow = StateGraph(BookingAgentState)

# Add nodes
workflow.add_node("collect_booking_details", collect_booking_details)
workflow.add_node("validate_booking_details", validate_booking_details)
workflow.add_node("check_availability", check_availability)
workflow.add_node("ask_for_missing_details", ask_for_missing_details)
workflow.add_node("ask_for_customer_name", ask_for_customer_name)
workflow.add_node("retry_customer_name", retry_customer_name)
workflow.add_node("collect_customer_name", collect_customer_name)
workflow.add_node("confirm_booking", confirm_booking)
workflow.add_node("classify_booking_confirmation", classify_booking_confirmation)
workflow.add_node("finalize_booking", finalize_booking)
workflow.add_node("cancel_booking", cancel_booking)

# Add edges
workflow.add_edge(START, "collect_booking_details")
workflow.add_edge("finalize_booking", END)
workflow.add_edge("cancel_booking", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
