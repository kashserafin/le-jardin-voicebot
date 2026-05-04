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
        },
        request_config,
    )

    interrupts = result.get("__interrupts__")
    if interrupts:
        return interrupts[0].value
    
    is_available = result.get("availability")
    
    if is_available:
        return "Booking confirmed! See you then."
    elif is_available is False:
        return "Sorry, we don't have availability for that time."
    else:
        return "Sorry, something went wrong. Please try again."
