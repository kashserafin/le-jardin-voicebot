from agent.state import BookingValidationIssue


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
                validation_messages.append("the date you provided is in the past")
            case "date_too_far_in_future":
                validation_messages.append("we only accept bookings up to two weeks from today")
            case "outside_opening_hours":
                validation_messages.append("our opening hours are from 12 PM to 10 PM")
            case "too_large_party_size":
                validation_messages.append("we can only take bookings for up to 10 people")
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
            "Absolutely, I can help with that. "
            f"Could you please tell me {join_human_readable(missing_details)}?"
        )

    if validation_messages and missing_details:
        return (
            f"Sorry, {join_human_readable(validation_messages)}. "
            f"Could you please tell me {join_human_readable(missing_details)}?"
        )

    if validation_messages:
        return f"Sorry, {join_human_readable(validation_messages)}. Could you please try again?"

    return ""
