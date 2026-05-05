from datetime import datetime

from agent.booking_guardrails import DATE_FORMAT, TIME_FORMAT
from agent.state import BookingDetails, BookingValidationIssue


def join_human_readable(items: list[str]) -> str:
    """Join a list of strings into a human-readable string with commas and 'and'."""
    
    if len(items) < 2:
        return "".join(items)
    
    if len(items) == 2:
        return " and ".join(items)
    
    all_but_last = ", ".join(items[:-1])

    return f"{all_but_last}, and {items[-1]}"


def build_missing_details_question(missing_fields: list[str], validation_errors: list[BookingValidationIssue]) -> str:
    """Build a question to ask the user for missing or invalid booking details."""
    
    missing_field_questions = {
        "date": "the day you'd like to come in",
        "time": "what time you'd like",
        "party_size": "how many guests are coming",
    }
    invalid_field_names = {
        "date": "the date",
        "time": "the time",
        "party_size": "the number of guests",
    }

    validation_messages = []
    generic_invalid_fields = []

    for error in validation_errors:
        match error["reason"]:
            case "date_in_past":
                validation_messages.append("that date has already passed")
            case "date_too_far_in_future":
                validation_messages.append("I can only book up to two weeks ahead")
            case "outside_opening_hours":
                validation_messages.append("our opening hours are from 12 PM to 10 PM")
            case "too_large_party_size":
                validation_messages.append("I can book up to 10 guests")
            case _:
                generic_invalid_fields.append(invalid_field_names.get(error["field"]))
    
    if generic_invalid_fields:
        validation_messages.append(
            f"I didn't quite catch {join_human_readable(generic_invalid_fields)}"
        )

    missing_details = [
        missing_field_questions[field]
        for field in ("date", "time", "party_size")
        if field in missing_fields
    ]

    if missing_details and not validation_messages:
        return (
            "Sure, I just need a few more details. "
            "Could you please tell me {join_human_readable(missing_details)}?"
        )

    if validation_messages and missing_details:
        return (
            f"Sorry, {join_human_readable(validation_messages)}. "
            f"Could you please tell me {join_human_readable(missing_details)}?"
        )

    if validation_messages:
        return f"Sorry, {join_human_readable(validation_messages)}. Could you please try again?"

    return ""


def format_booking_date_for_speech(value: str | None) -> str:
    """Format a canonical DD-MM-YYYY date for natural spoken output."""

    if value is None:
        return ""

    try:
        booking_date = datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        return value

    return f"{booking_date.strftime('%A')}, {booking_date.day} {booking_date.strftime('%B')}"


def format_booking_time_for_speech(value: str | None) -> str:
    """Format a canonical HH:MM time for natural spoken output."""

    if value is None:
        return ""

    try:
        booking_time = datetime.strptime(value, TIME_FORMAT).time()
    except ValueError:
        return value

    hour = booking_time.hour % 12 or 12
    suffix = "AM" if booking_time.hour < 12 else "PM"
    if booking_time.minute == 0:
        return f"{hour} {suffix}"

    return f"{hour}:{booking_time.minute:02d} {suffix}"


def build_booking_confirmation_question(booking_details: BookingDetails, customer_name: str) -> str:
    """Build a confirmation question to confirm the booking details with the user before finalizing the booking."""

    guest_label = "guest" if booking_details.party_size == 1 else "guests"
    spoken_date = format_booking_date_for_speech(booking_details.date)
    spoken_time = format_booking_time_for_speech(booking_details.time)

    return (
        f"Just to confirm, I've got {booking_details.party_size} "
        f"{guest_label} on {spoken_date} at {spoken_time}, "
        f"under the name {customer_name}, is that correct?"
    )
