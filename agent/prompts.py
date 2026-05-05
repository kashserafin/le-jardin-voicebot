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
