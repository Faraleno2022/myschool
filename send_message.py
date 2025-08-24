# Download the helper library from https://www.twilio.com/docs/python/install

import os
from twilio.rest import Client

# Credentials from env (do not hardcode)
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
if not account_sid or not auth_token:
    raise SystemExit("Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN in environment")

client = Client(account_sid, auth_token)

# Prefer Messaging Service if provided; else use direct FROM
messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
to_number = os.getenv("TWILIO_TEST_TO", "+18777804236")  # override in env
body = os.getenv("TWILIO_TEST_BODY", "[TEST] SMS via Messaging Service")

# Fallback direct FROM (when no MG). Provide your Twilio SMS number in env.
from_number = os.getenv("TWILIO_FROM_SMS") or os.getenv("TWILIO_FROM")

kwargs = {
    "to": to_number,
    "body": body,
}
if messaging_service_sid:
    kwargs["messaging_service_sid"] = messaging_service_sid
else:
    if not from_number:
        raise SystemExit("Missing sender: set TWILIO_MESSAGING_SERVICE_SID or TWILIO_FROM_SMS/TWILIO_FROM")
    kwargs["from_"] = from_number

msg = client.messages.create(**kwargs)
print(msg.sid)
