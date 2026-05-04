from pydantic import BaseModel, Field


class BookingDetails(BaseModel):
	date: str | None = Field(None, description="Real booking date in DD-MM-YYYY format.", example="25-12-2024")
	time: str | None = Field(None, description="Real booking time in HH:MM format.", example="19:30")
	party_size: int | None = Field(None, ge=1, le=10, description="Number of people (1-10)", example=4)


class CustomerDetails(BaseModel):
    name: str | None = Field(None, description="Customer name for the table booking", example="Smith")


class BookingAgentState(BaseModel):
    last_message: str
    booking_details: BookingDetails | None
    availability: bool | None
    customer_name: str | None
