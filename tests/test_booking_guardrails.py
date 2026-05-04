from datetime import date

import pytest

from agent.booking_guardrails import (
	BookingValidationError,
	validate_booking_date,
	validate_booking_time,
	validate_party_size,
)


REFERENCE_DATE = date(2026, 4, 30)


@pytest.mark.parametrize(
	("value", "expected"),
	[
		("30-04-2026", "30-04-2026"),
		("14-05-2026", "14-05-2026"),
	],
)
def test_accepts_booking_dates_in_window(value, expected):
	assert validate_booking_date(value, REFERENCE_DATE) == expected


@pytest.mark.parametrize("value", ["31-04-2026", "29-04-2026", "15-05-2026", "1-05-2026"])
def test_rejects_impossible_past_too_far_and_loose_dates(value):
	with pytest.raises(BookingValidationError):
		validate_booking_date(value, REFERENCE_DATE)


@pytest.mark.parametrize(("value", "expected"), [("12:00", "12:00"), ("22:00", "22:00")])
def test_accepts_opening_hours_boundaries(value, expected):
	assert validate_booking_time(value) == expected


@pytest.mark.parametrize("value", ["25:00", "11:59", "22:01", "7:00"])
def test_rejects_impossible_closed_and_loose_times(value):
	with pytest.raises(BookingValidationError):
		validate_booking_time(value)


@pytest.mark.parametrize(("value", "expected"), [(1, 1), (10, 10)])
def test_accepts_party_size_boundaries(value, expected):
	assert validate_party_size(value) == expected


@pytest.mark.parametrize("value", [0, 11, "many"])
def test_rejects_invalid_party_sizes(value):
	with pytest.raises(BookingValidationError):
		validate_party_size(value)
