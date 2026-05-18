from typing import Literal, TypedDict

from pydantic import BaseModel, Field


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
    intent: Literal["confirm", "decline", "change_request", "unclear"] = Field(
        ..., 
        description="Whether the user confirms the booking, declines it, asks to change it, "
        "or gives an unclear answer."
    )


class BookingValidationIssue(TypedDict):
    field: str
    value: str
    message: str
    reason: str
    example: str


BookingStatus = Literal["confirmed", "cancelled"]

BookingPhase = Literal["booking_details", "customer_name", "confirmation", "change_request", "done"] 

TurnIntent = Literal["phase_input", "restart", "cancel", "help", "out_of_scope", "unclear"]


class TurnIntentDecision(BaseModel):
     intent: TurnIntent = Field(
        ...,
        description="The routing intent for this turn: either current phase input, "
        "a global command, out-of-scope input, or unclear input."
    )


class BookingAgentState(TypedDict):
    last_message: str
    booking_details: BookingDetails | None
    availability: bool | None
    customer_name: str | None
    missing_details: list[str] | None
    validation_errors: list[BookingValidationIssue] | None
    booking_status: BookingStatus | None
    phase: BookingPhase | None
    turn_intent: TurnIntent | None
