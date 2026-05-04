from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.booking_guardrails import booking_rules_summary
from agent.state import BookingAgentState, BookingDetails
from agent.prompts import BOOKING_DETAILS_PROMPT
from config import settings


INITIAL_MESSAGE = "Welcome to Le Jardin! How may I help you?"


llm = ChatOpenAI(api_key=settings.openai_api_key, model="gpt-5-mini")


def collect_booking_details(
	state: BookingAgentState,
) -> Command[Literal["validate_booking_details"]]:

    structured_llm = llm.with_structured_output(BookingDetails)

    current_bd = state.booking_details or BookingDetails()

    try:
        new_bd = structured_llm.invoke(BOOKING_DETAILS_PROMPT.format(booking_rules=booking_rules_summary(), last_message=state.last_message))

        merged_bd = BookingDetails(
            date=new_bd.date if new_bd is not None else current_bd.date,
            time=new_bd.time if new_bd is not None else current_bd.time,
            party_size=new_bd.party_size if new_bd is not None else current_bd.party_size
        )
    except Exception as e:
        print(f"Error parsing booking details: {str(e)}")
        merged_bd = current_bd

    return Command(update={"booking_details":merged_bd}, goto="validate_booking_details")


def validate_booking_details(
	state: BookingAgentState,
) -> Command[Literal["check_availability", "ask_for_missing_details"]]:
    return {}


def check_availability(
	state: BookingAgentState,
) -> Command[Literal["confirm_booking"]]:
    return {}


def ask_for_missing_details(
	state: BookingAgentState,
) -> Command[Literal["collect_booking_details"]]:
    return {}


# def ask_for_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_customer_name"]]:
#     pass


# def collect_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["confirm_booking", "ask_for_customer_name"]]:
#     pass


def confirm_booking(state: BookingAgentState):
    return {}


# Create the graph
workflow = StateGraph(BookingAgentState)

# Add nodes
workflow.add_node("collect_booking_details", collect_booking_details)
workflow.add_node("validate_booking_details", validate_booking_details)
workflow.add_node("check_availability", check_availability)
workflow.add_node("ask_for_missing_details", ask_for_missing_details)
# workflow.add_node("ask_for_customer_name", ask_for_customer_name)
# workflow.add_node("collect_customer_name", collect_customer_name)
workflow.add_node("confirm_booking", confirm_booking)

# Add edges
workflow.add_edge(START, "collect_booking_details")
workflow.add_edge("confirm_booking", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
