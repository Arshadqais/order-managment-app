from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from support.models import Ticket


class Command(BaseCommand):
    help = "Send queued customer completion emails."

    def handle(self, *args, **options):
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            raise CommandError("Set EMAIL_HOST and DEFAULT_FROM_EMAIL.")

        status = Ticket.EmailStatus
        queued = Ticket.objects.filter(email_status=status.QUEUED)
        for ticket in queued.order_by("completed_at", "pk")[:50]:
            if not queued.filter(pk=ticket.pk).update(email_status=status.SENDING):
                continue
            try:
                sent = send_mail(
                    f"Support complaint #{ticket.pk} completed",
                    f"Future Advanced Technologies has completed work on your support complaint #{ticket.pk}.",
                    settings.DEFAULT_FROM_EMAIL,
                    [ticket.email],
                )
            except (SMTPException, OSError, ValueError):
                sent = 0
            result = status.ACCEPTED if sent == 1 else status.UNKNOWN
            Ticket.objects.filter(pk=ticket.pk).update(email_status=result)
            self.stdout.write(f"Complaint #{ticket.pk}: {result}")
