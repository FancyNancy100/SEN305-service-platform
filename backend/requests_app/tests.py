from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Category, ServiceRequest

User = get_user_model()


class ServiceRequestValidationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="tester",
            password="pass123"
        )

        self.category = Category.objects.create(
            name="IT Support"
        )

    def test_resolved_request_requires_fields(self):
        request = ServiceRequest(
            requester=self.user,
            category=self.category,
            title="Issue",
            description="Problem",
            location="Lab",
            status=ServiceRequest.Status.RESOLVED,
        )

        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_open_request_is_valid_without_resolution(self):
        request = ServiceRequest(
            requester=self.user,
            category=self.category,
            title="Issue",
            description="Problem",
            location="Lab",
            status=ServiceRequest.Status.OPEN,
        )

        request.full_clean()