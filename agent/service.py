from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.types import Command

from agent.graph import app
from config import settings


langfuse_client = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    base_url=settings.langfuse_base_url,
)

langfuse_handler = CallbackHandler(public_key=settings.langfuse_public_key)


def build_config(thread_id: str):
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "callbacks": [langfuse_handler],
    }
    

def run_next_turn(message: str, thread_id: str) -> str:
    request_config = build_config(thread_id)
    snapshot = app.get_state(request_config)

    if snapshot.next:
        result = app.invoke(Command(resume=message), request_config)
    else:
        result = app.invoke(
        {
            "last_message": message,
            "booking_details": None,
            "availability": None,
            "customer_name": None,
            "missing_details": None,
            "validation_errors": None,
            "booking_status": None,
        },
        request_config,
    )

    interrupts = result.get("__interrupt__")
    if interrupts:
        return interrupts[0].value
    
    booking_status = result.get("booking_status")

    match booking_status:
        case "confirmed":
            return "Booking confirmed! See you then."
        case "cancelled":
            return "No problem, your booking has been cancelled. Let us know if you change your mind!"
        case _:
            return "Sorry, something went wrong. Please try again."
