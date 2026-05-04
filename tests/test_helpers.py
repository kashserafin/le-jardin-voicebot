from agent.helpers import build_missing_details_question


def validation_issue(field: str, reason: str) -> dict[str, str]:
    return {
        "field": field,
        "value": "bad value",
        "message": "Original guardrail message.",
        "reason": reason,
        "example": "example value",
    }


def test_missing_fields_only_uses_booking_prompt():
    question = build_missing_details_question(
        ["date", "party_size"],
        [],
    )

    assert question == (
        "Absolutely, I can help with that. "
        "Could you please tell me the day you'd like to come in and how many guests are coming?"
    )


def test_explicit_validation_errors_only_explain_the_issues():
    question = build_missing_details_question(
        [],
        [
            validation_issue("date", "date_in_past"),
            validation_issue("time", "outside_opening_hours"),
            validation_issue("party_size", "too_large_party_size"),
        ],
    )

    assert question == (
        "Sorry, the date you provided is in the past, "
        "our opening hours are from 12 PM to 10 PM, "
        "and we can only take bookings for up to 10 people. "
        "Could you please try again?"
    )


def test_generic_validation_errors_only_use_did_not_catch_prompt():
    question = build_missing_details_question(
        [],
        [
            validation_issue("date", "invalid_format"),
            validation_issue("party_size", "too_small_party_size"),
        ],
    )

    assert question == (
        "Sorry, I didn't quite catch the date and the number of guests. "
        "Could you please try again?"
    )


def test_explicit_and_generic_validation_errors_are_combined():
    question = build_missing_details_question(
        [],
        [
            validation_issue("date", "date_too_far_in_future"),
            validation_issue("time", "invalid_format"),
        ],
    )

    assert question == (
        "Sorry, we only accept bookings up to two weeks from today "
        "and I didn't quite catch the time. Could you please try again?"
    )


def test_validation_errors_and_missing_fields_use_separate_follow_up():
    question = build_missing_details_question(
        ["time", "party_size"],
        [validation_issue("date", "date_too_far_in_future")],
    )

    assert question == (
        "Sorry, we only accept bookings up to two weeks from today. "
        "Could you please tell me what time you'd like and how many guests are coming?"
    )
