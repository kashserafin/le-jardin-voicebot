from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.types import Command

from agent.graph import app, build_initial_state
from config import settings


def create_langfuse_client() -> Langfuse | None:
    if not settings.langfuse_enabled:
        return None

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )


langfuse_client = create_langfuse_client()
langfuse_handler = (
    CallbackHandler(public_key=settings.langfuse_public_key)
    if langfuse_client
    else None
)


def build_config(thread_id: str):
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

    return config


def run_next_turn(message: str, thread_id: str) -> str:
    request_config = build_config(thread_id)
    snapshot = app.get_state(request_config)

    if snapshot.next:
        result = app.invoke(Command(resume=message), request_config)
    else:
        result = app.invoke(
            build_initial_state(message),
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
            return "No problem, I won't make that booking. Let us know if you change your mind!"
        case _:
            return "Sorry, I hit a snag. Please try again."
