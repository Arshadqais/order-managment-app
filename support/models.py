from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class Mode(models.TextChoices):
        REMOTE = "remote", "Remote / office support"
        ONSITE = "onsite", "On-site visit"

    class SmsStatus(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending or awaiting confirmation"
        ACCEPTED = "accepted", "Accepted by SMS provider"
        FAILED = "failed", "Rejected by SMS provider"
        INVALID = "invalid", "Invalid customer phone number"
        UNKNOWN = "unknown", "Delivery submission unconfirmed"

    class EmailStatus(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending or awaiting confirmation"
        ACCEPTED = "accepted", "Accepted by email server"
        UNKNOWN = "unknown", "Email submission unconfirmed"

    customer = models.CharField(max_length=120, verbose_name="Full name")
    email = models.EmailField(blank=True, verbose_name="Email address")
    phone = models.CharField(max_length=35, verbose_name="Phone number")
    address = models.CharField(max_length=300, verbose_name="Property / office number")
    description = models.TextField(max_length=2000, verbose_name="Describe the issue")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    mode = models.CharField(max_length=10, choices=Mode.choices, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    completed_at = models.DateTimeField(null=True, db_index=True)
    resolution = models.TextField(max_length=2000, blank=True)

    sms_status = models.CharField(max_length=10, choices=SmsStatus.choices, blank=True, db_index=True)

    email_status = models.CharField(max_length=10, choices=EmailStatus.choices, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class ComplaintPhoto(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="photo")
    image = models.BinaryField()


class RateBucket(models.Model):
    key = models.CharField(max_length=128, primary_key=True)
    hits = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
