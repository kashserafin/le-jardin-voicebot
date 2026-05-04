from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.state import BookingAgentState, BookingDetails
from agent.prompts import BOOKING_DETAILS_PROMPT
from config import settings


INITIAL_MESSAGE = "Welcome to Le Jardin! How may I help you?"


llm = ChatOpenAI(api_key=settings.openai_api_key, model="gpt-5-mini")


def collect_booking_details(
	state: BookingAgentState,
) -> Command[Literal["confirm_booking"]]:

    structured_llm = llm.with_structured_output(BookingDetails)
    structured_llm.invoke(BOOKING_DETAILS_PROMPT.format(booking_rules="", last_message=state.last_message))

    return Command(goto="confirm_booking")


# def ask_for_missing_details(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_booking_details"]]:
#     pass


# def check_availability(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_customer_name", "confirm_booking"]]:
#     pass


# def ask_for_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["collect_customer_name"]]:
#     pass


# def collect_customer_name(
# 	state: BookingAgentState,
# ) -> Command[Literal["confirm_booking", "ask_for_customer_name"]]:
#     pass


def confirm_booking(state: BookingAgentState):
    pass


# Create the graph
workflow = StateGraph(BookingAgentState)

# Add nodes
workflow.add_node("collect_booking_details", collect_booking_details)
# workflow.add_node("ask_for_missing_details", ask_for_missing_details)
# workflow.add_node("check_availability", check_availability)
# workflow.add_node("ask_for_customer_name", ask_for_customer_name)
# workflow.add_node("collect_customer_name", collect_customer_name)
workflow.add_node("confirm_booking", confirm_booking)

# Add edges
workflow.add_edge(START, "collect_booking_details")
workflow.add_edge("confirm_booking", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
