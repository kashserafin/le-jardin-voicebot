from datetime import date, datetime, time, timedelta

DATE_FORMAT = "%d-%m-%Y"
TIME_FORMAT = "%H:%M"
MAX_ADVANCE_DAYS = 14
OPENING_TIME = time(12, 0)
CLOSING_TIME = time(22, 0)
MIN_PARTY_SIZE = 1
MAX_PARTY_SIZE = 10


class BookingValidationError(ValueError):
	def __init__(self, field: str, message: str, reason: str):
		super().__init__(message)
		self.field = field
		self.message = message
		self.reason = reason


def today() -> date:
	return datetime.now().date()


def format_booking_date(value: date) -> str:
	return value.strftime(DATE_FORMAT)


def format_booking_time(value: time) -> str:
	return value.strftime(TIME_FORMAT)


def booking_date_window(reference_date: date | None = None) -> tuple[date, date]:
	start = reference_date or today()
	return start, start + timedelta(days=MAX_ADVANCE_DAYS)


def booking_rules_summary(reference_date: date | None = None) -> str:
	start, end = booking_date_window(reference_date)
	return (
		f"Bookings are accepted from {format_booking_date(start)} through "
		f"{format_booking_date(end)}, inclusive.\n Opening hours are "
		f"{format_booking_time(OPENING_TIME)}-{format_booking_time(CLOSING_TIME)}, inclusive.\n"
		f"Party size must be between {MIN_PARTY_SIZE} and {MAX_PARTY_SIZE} people."
	)


def validate_booking_date(value: str | None, reference_date: date | None = None) -> str | None:
	if value is None:
		return None

	raw_value = value.strip()
	try:
		booking_date = datetime.strptime(raw_value, DATE_FORMAT).date()
	except ValueError as exc:
		raise BookingValidationError(
			"date",
			"Date must be a real calendar date in DD-MM-YYYY format.",
			"invalid_format",
		) from exc

	if raw_value != format_booking_date(booking_date):
		raise BookingValidationError(
			"date",
			"Date must be a real calendar date in DD-MM-YYYY format.",
			"invalid_format",
		)

	start, end = booking_date_window(reference_date)
	if booking_date < start:
		raise BookingValidationError(
			"date",
			f"Date must be today or later. Earliest accepted date is {format_booking_date(start)}.",
			"date_in_past",
		)
	if booking_date > end:
		raise BookingValidationError(
			"date",
			f"Date must be within the next {MAX_ADVANCE_DAYS} days. "
			f"Latest accepted date is {format_booking_date(end)}.",
			"date_too_far_in_future",
		)

	return format_booking_date(booking_date)


def validate_booking_time(value: str | None) -> str | None:
	if value is None:
		return None

	raw_value = value.strip()
	try:
		booking_time = datetime.strptime(raw_value, TIME_FORMAT).time()
	except ValueError as exc:
		raise BookingValidationError(
			"time",
			"Time must be a real clock time in HH:MM format.",
			"invalid_format",
		) from exc

	if raw_value != format_booking_time(booking_time):
		raise BookingValidationError(
			"time",
			"Time must be a real clock time in HH:MM format.",
			"invalid_format",
		)

	if booking_time < OPENING_TIME or booking_time > CLOSING_TIME:
		raise BookingValidationError(
			"time",
			f"Time must be between {format_booking_time(OPENING_TIME)} and "
			f"{format_booking_time(CLOSING_TIME)}.",
			"outside_opening_hours",
		)

	return format_booking_time(booking_time)


def validate_party_size(value: int | str | None) -> int | None:
	if value is None:
		return None

	try:
		party_size = int(value)
	except (TypeError, ValueError) as exc:
		raise BookingValidationError(
			"party_size",
			"Party size must be a whole number.",
			"invalid_format",  
		) from exc

	if party_size < MIN_PARTY_SIZE:
		raise BookingValidationError(
			"party_size",
			f"Party size must be between {MIN_PARTY_SIZE} and {MAX_PARTY_SIZE} people.",
			"too_small_party_size",
		)

	if party_size > MAX_PARTY_SIZE:
		raise BookingValidationError(
			"party_size",
			f"Party size must be between {MIN_PARTY_SIZE} and {MAX_PARTY_SIZE} people.",
			"too_large_party_size",
		)

	return party_size
