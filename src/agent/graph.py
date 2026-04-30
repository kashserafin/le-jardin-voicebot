from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.state import BookingAgentState


INITIAL_MESSAGE = "Welcome to Le Jardin! How may I help you?"


def collect_booking_details(
	state: BookingAgentState,
) -> Command[Literal["check_availability", "ask_for_missing_details"]]:
    pass


def ask_for_missing_details(
	state: BookingAgentState,
) -> Command[Literal["collect_booking_details"]]:
    pass


def check_availability(
	state: BookingAgentState,
) -> Command[Literal["collect_customer_name", "confirm_booking"]]:
    pass


def ask_for_customer_name(
	state: BookingAgentState,
) -> Command[Literal["collect_customer_name"]]:
    pass


def collect_customer_name(
	state: BookingAgentState,
) -> Command[Literal["confirm_booking", "ask_for_customer_name"]]:
    pass


def confirm_booking(state: BookingAgentState):
    pass


# Create the graph
workflow = StateGraph(BookingAgentState)

# Add nodes
workflow.add_node("collect_booking_details", collect_booking_details)
workflow.add_node("ask_for_missing_details", ask_for_missing_details)
workflow.add_node("check_availability", check_availability)
workflow.add_node("ask_for_customer_name", ask_for_customer_name)
workflow.add_node("collect_customer_name", collect_customer_name)
workflow.add_node("confirm_booking", confirm_booking)

# Add edges
workflow.add_edge(START, "collect_booking_details")
workflow.add_edge("confirm_booking", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
