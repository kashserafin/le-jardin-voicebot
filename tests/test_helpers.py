from agent.helpers import (
    build_booking_confirmation_question,
    build_missing_details_question,
    format_booking_date_for_speech,
    format_booking_time_for_speech,
)
from agent.state import BookingDetails


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
        "Sure. "
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
        "Sorry, that date has already passed, "
        "our opening hours are from 12 PM to 10 PM, "
        "and I can book up to 10 guests. "
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
        "Sorry, I can only book up to two weeks ahead "
        "and I didn't quite catch the time. Could you please try again?"
    )


def test_validation_errors_and_missing_fields_use_separate_follow_up():
    question = build_missing_details_question(
        ["time", "party_size"],
        [validation_issue("date", "date_too_far_in_future")],
    )

    assert question == (
        "Sorry, I can only book up to two weeks ahead. "
        "Could you please tell me what time you'd like and how many guests are coming?"
    )


def test_formats_canonical_booking_date_for_speech():
    assert format_booking_date_for_speech("09-05-2026") == "Saturday, 9 May"


def test_formats_canonical_booking_time_for_speech():
    assert format_booking_time_for_speech("19:30") == "7:30 PM"
    assert format_booking_time_for_speech("12:00") == "12 PM"
    assert format_booking_time_for_speech("22:00") == "10 PM"


def test_booking_confirmation_question_uses_spoken_date_and_time():
    question = build_booking_confirmation_question(
        BookingDetails(date="09-05-2026", time="19:30", party_size=2),
        "Ada Lovelace",
    )

    assert question == (
        "Just to confirm, I've got 2 guests "
        "on Saturday, 9 May at 7:30 PM, under the name Ada Lovelace, "
        "is that correct?"
    )
