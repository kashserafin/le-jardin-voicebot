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
    
    spoken_fields = {
        "date": "the day you'd like to come in",
        "time": "what time you'd like",
        "party_size": "how many guest are coming"
    }

    if validation_errors:
        # TODO: add code for building a question based on validation errors
        return "I see there are some issues with the information you provided. Could you please clarify?"
    
    missing_details = [spoken_fields[field] for field in ("date", "time", "party_size") if field in missing_fields]

    return f"Absolutely, I can help with that. Could you please tell me {join_human_readable(missing_details)}?"
