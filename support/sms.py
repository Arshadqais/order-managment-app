import base64
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Ticket


def normalize_phone(value):
    number = re.sub(r"[\s().-]", "", value)
    if number.startswith("00"):
        number = "+" + number[2:]
    if re.fullmatch(r"03[0-9]{9}", number):
        number = "+92" + number[1:]
    if re.fullmatch(r"\+923[0-9]{9}|\+(?!92)[1-9][0-9]{7,14}", number):
        return number
    return None


def send_completion_sms(ticket, account_sid, auth_token, sender):
    status = Ticket.SmsStatus
    recipient = normalize_phone(ticket.phone)
    if recipient is None:
        return status.INVALID

    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode("ascii")
    message = f"Future Advanced Technologies: Work on your support complaint #{ticket.pk} is complete."
    request = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=urlencode({"From": sender, "To": recipient, "Body": message}).encode(),
        headers={"Authorization": f"Basic {auth}"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            return status.ACCEPTED if response.status == 201 else status.UNKNOWN
    except HTTPError as error:
        return status.FAILED if 400 <= error.code < 500 else status.UNKNOWN
    except (URLError, OSError):
        return status.UNKNOWN
