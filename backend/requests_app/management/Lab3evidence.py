
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from requests_app.models import Category, ServiceRequest

User = get_user_model()
PREFIX = "[LAB]"
Status = ServiceRequest.Status

# (title, category, priority, status, due in hours, age in hours)
SYNTHETIC_REQUESTS = [
    ("Due soon",             "Electrical", 2, Status.OPEN,     2,   30),
    ("Due later",            "Electrical", 4, Status.OPEN,     48,  28),
    ("Flickering light",     "Electrical", 1, Status.ASSIGNED, 5,   26),
    ("Dead power socket",    "Electrical", 3, Status.OPEN,     24,  24),
    ("Projector will not start", "Electrical", 2, Status.ASSIGNED, 72, 20),
    ("Generator noise",      "Electrical", 5, Status.RESOLVED, -10, 18),
    ("Broken fan",           "Electrical", 3, Status.RESOLVED, -20, 16),
    ("Leaking tap",          "Plumbing",   2, Status.OPEN,     8,   14),
    ("Blocked drain",        "Plumbing",   1, Status.ASSIGNED, 12,  12),
    ("Low water pressure",   "Plumbing",   4, Status.OPEN,     96,  10),
    ("Toilet will not flush", "Plumbing",  1, Status.RESOLVED, -5,  8),
    ("Burst pipe",           "Plumbing",   5, Status.ASSIGNED, 3,   6),
]


class Command(BaseCommand):
    help = "Create synthetic lab data and print the due-date and query-analysis evidence."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete the synthetic lab data and exit.",
        )

    def handle(self, *args, **options):
        self.remove_synthetic_data()
        if options["clear"]:
            self.stdout.write(self.style.SUCCESS("Synthetic lab data removed."))
            return

        user, categories = self.create_synthetic_data()
        self.show_due_date_query()
        self.show_query_analysis(categories["Electrical"])
        self.stdout.write(
            "\nRun  python manage.py lab3_evidence --clear  to remove the lab data."
        )

    # ------------------------------------------------------------------ data

    def remove_synthetic_data(self):
        ServiceRequest.objects.filter(title__startswith=PREFIX).delete()
        Category.objects.filter(name__startswith=PREFIX).delete()
        User.objects.filter(username="lab_user").delete()

    def create_synthetic_data(self):
        now = timezone.now()
        user = User.objects.create_user(username="lab_user")
        user.set_unusable_password()
        user.save()

        categories = {
            name: Category.objects.create(name=f"{PREFIX} {name}")
            for name in ("Electrical", "Plumbing")
        }

        for title, category, priority, status, due_hours, age_hours in SYNTHETIC_REQUESTS:
            request = ServiceRequest(
                requester=user,
                category=categories[category],
                title=f"{PREFIX} {title}",
                description="Synthetic laboratory data.",
                location="Laboratory",
                priority=priority,
                status=status,
                due_at=now + timedelta(hours=due_hours),
            )
            if status == Status.RESOLVED:
                request.resolved_at = now
                request.resolution_summary = "Fixed during the laboratory exercise."
            request.full_clean()          # proves the model rule on every record
            request.save()
            # created_at is set automatically, so spread the dates with an update
            ServiceRequest.objects.filter(pk=request.pk).update(
                created_at=now - timedelta(hours=age_hours)
            )

        self.heading("Synthetic data created")
        self.stdout.write(f"{len(SYNTHETIC_REQUESTS)} requests in 2 categories.")
        for status in (Status.OPEN, Status.ASSIGNED, Status.RESOLVED):
            count = ServiceRequest.objects.filter(
                title__startswith=PREFIX, status=status
            ).count()
            self.stdout.write(f"  {status.label}: {count}")
        return user, categories

    # ------------------------------------------------------ Task 1, step 5

    def show_due_date_query(self):
        chosen_time = timezone.now() + timedelta(hours=6)
        queryset = ServiceRequest.objects.filter(
            title__startswith=PREFIX, due_at__lt=chosen_time
        ).order_by("due_at")

        self.heading("Task 1: requests due before the chosen time")
        self.stdout.write(f"Chosen time: {chosen_time:%Y-%m-%d %H:%M} (6 hours from now)")
        for request in queryset:
            self.stdout.write(f"  due {request.due_at:%Y-%m-%d %H:%M}  {request.title}")
        self.stdout.write(f"Total: {queryset.count()}")

    # ---------------------------------------------------------------- Task 3

    def show_query_analysis(self, category):
        queryset = ServiceRequest.objects.filter(
            category=category,
            status__in=[Status.OPEN, Status.ASSIGNED],
        ).order_by("priority", "created_at")

        self.heading("Task 3: open or assigned requests in one category")
        self.stdout.write("Rows returned (ordered by priority, then created date):")
        for request in queryset:
            self.stdout.write(
                f"  priority {request.priority}  {request.status:9}  {request.title}"
            )

        self.heading("queryset.query (generated SQL)")
        self.stdout.write(str(queryset.query))

        self.heading("queryset.explain()")
        self.stdout.write(queryset.explain())

        self.stdout.write(
            "\nHow to read it: look at the 'key' column (MySQL) or the 'USING INDEX' "
            "text (SQLite). If it names req_cat_status_idx, that index is used. If it "
            "says NULL / SCAN, the table is so small that reading every row is cheaper."
        )

    def heading(self, text):
        self.stdout.write(f"\n=== {text} ===")