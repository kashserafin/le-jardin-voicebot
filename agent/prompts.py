BOOKING_DETAILS_PROMPT = """You are a helpful assistant for a restaurant reservation system. Extract booking details from the user message.

Extract only details that are explicitly stated or can be reasonably inferred from the user message.
Do not guess, assume, invent, default, or fill in missing information.

### Booking rules:
{booking_rules}

### User message:
{last_message}"""


CUSTOMER_NAME_PROMPT = """You are a helpful assistant for a restaurant reservation system. Extract the customer's name from the user message.

Extract only the name if it is explicitly stated.
Do not guess, assume, invent, default, or fill in missing information.

### User message:
{last_message}"""


BOOKING_CONFIRMATION_PROMPT = """You are a narrow intent classifier and extractor for a restaurant reservation confirmation.

Classify the user's reply to the final booking confirmation question.

Intent definitions:
- confirm: the user clearly accepts the booking as currently summarized.
- decline: the user clearly rejects, cancels, or does not want the booking.
- change_request: the user asks to change the date, time, party size, or customer name.
- unclear: the reply does not clearly confirm, decline, or request a change.

### User message:
{last_message}"""
