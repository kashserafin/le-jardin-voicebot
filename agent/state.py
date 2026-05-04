from typing import TypedDict

from pydantic import BaseModel, Field


class BookingDetails(BaseModel):
	date: str | None = Field(None, description="Booking date in DD-MM-YYYY format.", example="25-12-2024")
	time: str | None = Field(None, description="Booking time in HH:MM format.", example="19:30")
	party_size: int | None = Field(None, description="Number of people", example=4)


class CustomerDetails(BaseModel):
    name: str | None = Field(None, description="Customer name for the table booking", example="Smith")


class BookingValidationIssue(TypedDict):
    field: str
    value: str
    message: str
    example: str


class BookingAgentState(TypedDict):
    last_message: str
    booking_details: BookingDetails | None
    availability: bool | None
    customer_name: str | None
    missing_details: list[str] | None
    validation_errors: list[BookingValidationIssue] | None
