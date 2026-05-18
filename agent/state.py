from enum import StrEnum
from typing import TypedDict

from pydantic import BaseModel, Field


class BookingValidationIssue(TypedDict):
    field: str
    value: str
    message: str
    reason: str
    example: str


class BookingConfirmationIntent(StrEnum):
    CONFIRM = "confirm"
    DECLINE = "decline"
    CHANGE_REQUEST = "change_request"
    UNCLEAR = "unclear"


class BookingStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BookingPhase(StrEnum):
    BOOKING_DETAILS = "booking_details"
    CUSTOMER_NAME = "customer_name"
    CONFIRMATION = "confirmation"
    CHANGE_REQUEST = "change_request"
    DONE = "done"


class TurnIntent(StrEnum):
    PHASE_INPUT = "phase_input"
    RESTART = "restart"
    CANCEL = "cancel"
    HELP = "help"
    OUT_OF_SCOPE = "out_of_scope"
    UNCLEAR = "unclear"


class BookingDetails(BaseModel):
	date: str | None = Field(
        None,
        description="Booking date in DD-MM-YYYY format.",
        json_schema_extra={"example": "25-12-2024"}
    )
	time: str | None = Field(
        None,
        description="Booking time in HH:MM format.",
        json_schema_extra={"example": "19:30"}
    )
	party_size: int | None = Field(
        None,
        description="Number of people",
        json_schema_extra={"example": 4}
    )


class CustomerDetails(BaseModel):
    name: str | None = Field(
        None,
        description="Customer name for the table booking",
        json_schema_extra={"example": "Smith"}
    )


class BookingConfirmationDecision(BaseModel):
    intent: BookingConfirmationIntent = Field(
        ..., 
        description="Whether the user confirms the booking, declines it, asks to change it, "
        "or gives an unclear answer."
    )


class TurnIntentDecision(BaseModel):
     intent: TurnIntent = Field(
        ...,
        description="The routing intent for this turn: either current phase input, "
        "a global command, out-of-scope input, or unclear input."
    )


class BookingAgentState(TypedDict):
    """
    Persistent state for a single booking conversation turn.

    Fields:
    - last_message: The raw user input from the current turn.
    - booking_details: Collected booking fields such as date, time, and party size.
    - availability: Whether the selected slot is available for booking.
    - customer_name: The name supplied by the user for the reservation.
    - missing_details: Fields the agent still needs from the user to complete the booking.
    - validation_errors: Structured validation issues for any invalid booking inputs.
    - booking_status: The current booking lifecycle state, such as confirmed or cancelled.
    - phase: The current stage of the booking flow.
    - turn_intent: The high-level intent classification for the current user message.
    - reply_text: The next response the bot should send to the user.
    """
    last_message: str
    booking_details: BookingDetails | None
    availability: bool | None
    customer_name: str | None
    missing_details: list[str] | None
    validation_errors: list[BookingValidationIssue] | None
    booking_status: BookingStatus | None
    phase: BookingPhase | None
    turn_intent: TurnIntent | None
    reply_text: str | None
