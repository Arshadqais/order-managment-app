import os
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Ticket


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
            "customer": "Sample Customer", "phone": "03001234567",
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
        self.assertEqual(ticket.sms_status, Ticket.SmsStatus.QUEUED)
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
            self.assertEqual(message["To"], ["+923001234567"])
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
