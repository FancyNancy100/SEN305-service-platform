from django.contrib import admin
from django.utils import timezone

from .models import Category, Comment, ServiceRequest, WorkOrder


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("author", "body", "is_internal", "created_at")
    readonly_fields = ("created_at",)


class OverdueFilter(admin.SimpleListFilter):
    title = "overdue"
    parameter_name = "overdue"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Overdue"),
            ("no", "Not Overdue"),
        )

    def queryset(self, request, queryset):
        now = timezone.now()

        if self.value() == "yes":
            return queryset.filter(
                due_at__lt=now,
                status__in=["open", "assigned", "in_progress"],
            )

        if self.value() == "no":
            return queryset.exclude(
                due_at__lt=now,
                status__in=["open", "assigned", "in_progress"],
            )

        return queryset


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "requester",
        "priority",
        "status",
        "due_at",
        "created_at",
    )

    list_filter = (
        "status",
        "priority",
        "category",
        OverdueFilter,
    )

    search_fields = (
        "title",
        "description",
        "location",
        "requester__username",
        "resolution_summary",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "requester",
    )