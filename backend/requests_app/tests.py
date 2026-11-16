from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, ServiceRequest

User = get_user_model()


class ServiceRequestValidationTests(TestCase):
    """Task 2: a resolved or closed request needs resolved_at and a summary."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass123")
        self.category = Category.objects.create(name="IT Support")

    def make_request(self, **overrides):
        """Build an unsaved request with valid defaults; overrides change fields."""
        values = {
            "requester": self.user,
            "category": self.category,
            "title": "Issue",
            "description": "Problem",
            "location": "Lab",
            "status": ServiceRequest.Status.OPEN,
        }
        values.update(overrides)
        return ServiceRequest(**values)

    # --- original tests ---------------------------------------------------

    def test_resolved_request_requires_fields(self):
        request = self.make_request(status=ServiceRequest.Status.RESOLVED)
        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_open_request_is_valid_without_resolution(self):
        self.make_request(status=ServiceRequest.Status.OPEN).full_clean()

    # --- new tests --------------------------------------------------------

    def test_resolved_without_resolved_at_fails(self):
        request = self.make_request(
            status=ServiceRequest.Status.RESOLVED,
            resolution_summary="Replaced the faulty cable.",
        )
        with self.assertRaises(ValidationError) as ctx:
            request.full_clean()
        self.assertIn("resolved_at", ctx.exception.message_dict)
        self.assertNotIn("resolution_summary", ctx.exception.message_dict)

    def test_resolved_without_summary_fails(self):
        request = self.make_request(
            status=ServiceRequest.Status.RESOLVED,
            resolved_at=timezone.now(),
        )
        with self.assertRaises(ValidationError) as ctx:
            request.full_clean()
        self.assertIn("resolution_summary", ctx.exception.message_dict)
        self.assertNotIn("resolved_at", ctx.exception.message_dict)

    def test_whitespace_only_summary_is_rejected(self):
        request = self.make_request(
            status=ServiceRequest.Status.RESOLVED,
            resolved_at=timezone.now(),
            resolution_summary="   ",
        )
        with self.assertRaises(ValidationError) as ctx:
            request.full_clean()
        self.assertIn("resolution_summary", ctx.exception.message_dict)

    def test_closed_without_both_fields_reports_both_errors(self):
        request = self.make_request(status=ServiceRequest.Status.CLOSED)
        with self.assertRaises(ValidationError) as ctx:
            request.full_clean()
        self.assertIn("resolved_at", ctx.exception.message_dict)
        self.assertIn("resolution_summary", ctx.exception.message_dict)

    def test_resolved_with_both_fields_is_valid(self):
        self.make_request(
            status=ServiceRequest.Status.RESOLVED,
            resolved_at=timezone.now(),
            resolution_summary="Replaced the faulty cable.",
        ).full_clean()

    def test_closed_with_both_fields_is_valid(self):
        self.make_request(
            status=ServiceRequest.Status.CLOSED,
            resolved_at=timezone.now(),
            resolution_summary="Closed after user confirmed the fix.",
        ).full_clean()

    def test_in_progress_does_not_need_resolution_data(self):
        self.make_request(status=ServiceRequest.Status.IN_PROGRESS).full_clean()

    def test_priority_outside_one_to_five_fails(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_request(priority=6).full_clean()
        self.assertIn("priority", ctx.exception.message_dict)


class DueDateTests(TestCase):
    """Task 1: nullable due_at, supporting index, query and admin filter."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass123")
        self.category = Category.objects.create(name="Electrical")
        self.now = timezone.now()

    def create_request(self, title, **overrides):
        values = {
            "requester": self.user,
            "category": self.category,
            "title": title,
            "description": "Synthetic lab data",
            "location": "Lab",
        }
        values.update(overrides)
        return ServiceRequest.objects.create(**values)

    def test_due_at_is_optional(self):
        request = self.create_request("No due date")
        request.full_clean()
        self.assertIsNone(request.due_at)

    def test_query_returns_only_requests_due_before_chosen_time(self):
        soon = self.create_request("Due soon", due_at=self.now + timedelta(hours=2))
        self.create_request("Due later", due_at=self.now + timedelta(days=2))

        chosen_time = self.now + timedelta(hours=12)
        results = ServiceRequest.objects.filter(due_at__lt=chosen_time)

        self.assertEqual(list(results), [soon])

    def test_requests_without_due_date_are_not_returned(self):
        self.create_request("No due date")
        self.create_request("Due soon", due_at=self.now + timedelta(hours=1))

        results = ServiceRequest.objects.filter(
            due_at__lt=self.now + timedelta(days=1)
        )
        self.assertEqual(results.count(), 1)

    def test_status_due_index_exists_in_database(self):
        table = ServiceRequest._meta.db_table
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)

        self.assertIn("req_status_due_idx", constraints)
        self.assertEqual(
            constraints["req_status_due_idx"]["columns"], ["status", "due_at"]
        )

    def test_admin_overdue_filter_shows_only_overdue_active_requests(self):
        self.create_request(
            "Overdue pump",
            status=ServiceRequest.Status.OPEN,
            due_at=self.now - timedelta(hours=3),
        )
        self.create_request(
            "Future lamp",
            status=ServiceRequest.Status.OPEN,
            due_at=self.now + timedelta(days=1),
        )
        self.create_request(
            "Resolved but late",
            status=ServiceRequest.Status.RESOLVED,
            due_at=self.now - timedelta(days=1),
            resolved_at=self.now,
            resolution_summary="Fixed.",
        )

        admin_user = User.objects.create_superuser(
            username="boss", email="boss@example.com", password="pass12345"
        )
        self.client.force_login(admin_user)

        url = reverse("admin:requests_app_servicerequest_changelist")
        response = self.client.get(url, {"overdue": "yes"})

        self.assertContains(response, "Overdue pump")
        self.assertNotContains(response, "Future lamp")
        self.assertNotContains(response, "Resolved but late")