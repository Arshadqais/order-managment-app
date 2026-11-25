import os
import re

from django.core.management.base import BaseCommand, CommandError

from support.models import Ticket
from support.sms import send_completion_sms


class Command(BaseCommand):
    help = "Send queued customer completion SMS notifications."

    def handle(self, *args, **options):
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        sender = os.environ.get("TWILIO_FROM_NUMBER")
        if not re.fullmatch(r"AC[0-9a-fA-F]{32}", account_sid) or not auth_token or not sender:
            raise CommandError(
                "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER."
            )

        status = Ticket.SmsStatus
        queued = Ticket.objects.filter(sms_status=status.QUEUED)
        for ticket in queued.order_by("completed_at", "pk")[:50]:
            if not queued.filter(pk=ticket.pk).update(sms_status=status.SENDING):
                continue
            result = send_completion_sms(ticket, account_sid, auth_token, sender)
            Ticket.objects.filter(pk=ticket.pk).update(sms_status=result)
            self.stdout.write(f"Complaint #{ticket.pk}: {result}")
