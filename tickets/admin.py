from django.contrib import admin

from .models import Ticket, TicketComment, TicketEvent


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0
    readonly_fields = ["author", "body", "is_internal", "created_at"]
    can_delete = False


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    readonly_fields = ["actor", "action", "changes", "created_at"]
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "title",
        "reporter",
        "assignee",
        "priority",
        "status",
        "created_at",
    ]
    list_filter = ["status", "priority", "category"]
    search_fields = [
        "title",
        "description",
        "reporter__email",
        "assignee__email",
        "area",
        "workstation",
    ]
    readonly_fields = ["created_at", "updated_at", "resolved_at"]
    inlines = [TicketCommentInline, TicketEventInline]


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "is_internal", "created_at"]
    readonly_fields = ["ticket", "author", "body", "is_internal", "created_at"]


@admin.register(TicketEvent)
class TicketEventAdmin(admin.ModelAdmin):
    list_display = ["ticket", "actor", "action", "created_at"]
    readonly_fields = ["ticket", "actor", "action", "changes", "created_at"]

