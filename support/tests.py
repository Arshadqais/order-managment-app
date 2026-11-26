import os
from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from PIL import Image

from .models import ComplaintPhoto, Ticket


class SupportWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_superuser("boss", password="admin-test-pass-728")
        cls.employee = users.create_user("technician", password="employee-test-pass-728")
        cls.other = users.create_user("other")

    def sign_in(self, portal, user, password):
        return self.client.post(reverse(portal), {
            "username": user.username, "password": password,
        })

    def test_complaint_to_filtered_work_history(self):
        self.assertContains(self.client.get(reverse("complaint")), "Submit a complaint")
        response = self.client.post(reverse("complaint"), {
            "customer": "Sample Customer", "phone": "050 123 4567",
            "email": "customer@example.com",
            "address": "Office 7", "description": "Wi-Fi disconnects",
        }, follow=True)
        ticket = Ticket.objects.get()
        self.assertContains(response, f"Your reference is #{ticket.pk}")
        detail = reverse("ticket", args=[ticket.pk])
        self.assertEqual(self.client.get(detail).status_code, 302)
        self.sign_in("admin-login", self.admin, "admin-test-pass-728")
        self.assertContains(self.client.get(reverse("queue")), "Sample Customer")
        self.client.post(detail, {"action": "route", "mode": "onsite"})
        self.client.logout()
        self.sign_in("employee-login", self.employee, "employee-test-pass-728")
        self.assertContains(self.client.get(reverse("queue")), "On-site visit")
        self.assertEqual(self.client.post(detail, {"action": "route", "mode": "remote"}).status_code, 403)
        self.client.post(detail, {"action": "complete", "resolution": "Replaced faulty router."})
        self.client.post(detail, {"action": "complete", "resolution": "Duplicate update."})
        ticket.refresh_from_db()
        self.assertEqual(ticket.completed_by, self.employee)
        self.assertEqual(ticket.mode, "onsite")
        self.assertEqual(ticket.resolution, "Replaced faulty router.")
        self.assertEqual(ticket.phone, "+971501234567")
        self.assertEqual(ticket.sms_status, Ticket.SmsStatus.QUEUED)
        self.assertEqual(ticket.email_status, Ticket.EmailStatus.QUEUED)
        with self.settings(EMAIL_HOST="smtp.example.com", DEFAULT_FROM_EMAIL="desk@example.com"):
            call_command("send_completion_email", stdout=StringIO())
            call_command("send_completion_email", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["customer@example.com"])
        self.assertIn(f"#{ticket.pk}", mail.outbox[0].subject)
        ticket.refresh_from_db()
        self.assertEqual(ticket.email_status, Ticket.EmailStatus.ACCEPTED)
        credentials = {
            "TWILIO_ACCOUNT_SID": "AC" + "0" * 32,
            "TWILIO_AUTH_TOKEN": "test-token",
            "TWILIO_FROM_NUMBER": "+15005550006",
        }
        with patch.dict(os.environ, credentials), patch("support.sms.urlopen") as send:
            send.return_value.__enter__.return_value.status = 201
            call_command("send_completion_sms", stdout=StringIO())
            call_command("send_completion_sms", stdout=StringIO())
            send.assert_called_once()
            message = parse_qs(send.call_args.args[0].data.decode())
            self.assertEqual(message["To"], ["+971501234567"])
            self.assertIn(f"#{ticket.pk}", message["Body"][0])
        ticket.refresh_from_db()
        self.assertEqual(ticket.sms_status, Ticket.SmsStatus.ACCEPTED)
        self.assertContains(self.client.get(reverse("queue"), {"view": "history"}), "Sample Customer")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_login(self.admin)
        date = timezone.localdate(ticket.completed_at).isoformat()
        response = self.client.get(reverse("queue"), {
            "view": "history", "employee": "technician", "start": date, "end": date,
        })
        self.assertContains(response, "Completed by technician")
        self.assertContains(self.client.get(detail), "Replaced faulty router.")
        response = self.client.get(reverse("queue"), {"view": "history", "employee": "other"})
        self.assertNotContains(response, "Sample Customer")

    def test_role_specific_logins_and_csrf(self):
        response = self.sign_in("admin-login", self.employee, "employee-test-pass-728")
        self.assertContains(response, "invalid for this portal")
        response = self.sign_in("employee-login", self.admin, "admin-test-pass-728")
        self.assertContains(response, "invalid for this portal")
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse("complaint")).status_code, 403)

    def test_public_submission_rate_limit(self):
        for _ in range(20):
            self.assertEqual(self.client.post(reverse("complaint")).status_code, 200)
        self.assertEqual(self.client.post(reverse("complaint")).status_code, 429)
        self.assertFalse(Ticket.objects.exists())

    def test_photo_upload_and_staff_access(self):
        image = BytesIO()
        Image.new("RGB", (80, 40), "red").save(image, "PNG")
        response = self.client.post(reverse("complaint"), {
            "customer": "Sample Customer", "phone": "050 123 4567",
            "email": "customer@example.com",
            "address": "Office 7", "description": "Wi-Fi disconnects",
            "photo": SimpleUploadedFile("screenshot.png", image.getvalue(), "image/png"),
        })
        self.assertRedirects(response, reverse("complaint"))
        ticket = Ticket.objects.get()
        url = reverse("complaint-photo", args=[ticket.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse("ticket", args=[ticket.pk])), "Attached photo")
        response = self.client.get(url)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("no-store", response["Cache-Control"])
        with Image.open(BytesIO(response.content)) as photo:
            self.assertEqual(photo.size, (80, 40))
        Ticket.objects.filter(pk=ticket.pk).update(
            completed_at=timezone.now(), completed_by=self.employee,
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        for user in (self.employee, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_invalid_or_oversized_photo_rejects_complaint(self):
        for photo, error in [
            (b"not an image", "Upload a valid JPEG, PNG or WebP image."),
            (b"x" * (5 * 1024 * 1024 + 1), "Choose a photo that is 5 MB or smaller."),
        ]:
            response = self.client.post(reverse("complaint"), {
                "customer": "Sample Customer", "phone": "050 123 4567",
                "email": "customer@example.com",
                "address": "Office 7", "description": "Wi-Fi disconnects",
                "photo": SimpleUploadedFile("screenshot.png", photo, "image/png"),
            })
            self.assertContains(response, error)
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(ComplaintPhoto.objects.exists())

    def test_invalid_contact_details_reject_complaint(self):
        response = self.client.post(reverse("complaint"), {
            "customer": "Sample Customer", "phone": "+92 300 123 4567",
            "email": "missing-at-sign", "address": "Office 7", "description": "Wi-Fi disconnects",
        })
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "Enter a UAE phone number")
        self.assertFalse(Ticket.objects.exists())

    def test_legacy_complaint_without_email_can_be_completed(self):
        ticket = Ticket.objects.create(
            customer="Legacy Customer", phone="03001234567",
            address="Office 7", description="Wi-Fi disconnects", mode=Ticket.Mode.REMOTE,
        )
        self.client.force_login(self.employee)
        response = self.client.post(reverse("ticket", args=[ticket.pk]), {
            "action": "complete", "resolution": "Reconnected the access point.",
        })
        self.assertRedirects(response, reverse("ticket", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.completed_by, self.employee)
        self.assertEqual(ticket.email_status, "")
