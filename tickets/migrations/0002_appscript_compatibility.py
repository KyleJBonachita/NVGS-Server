import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def convert_existing_tickets(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    status_map = {
        "new": "Open",
        "acknowledged": "In Progress",
        "assigned": "Assigned",
        "in_progress": "In Progress",
        "waiting_for_agent": "On Hold",
        "resolved": "Resolved",
        "closed": "Closed",
        "cancelled": "Closed",
    }
    priority_map = {
        "urgent": "Urgent",
        "high": "High",
        "normal": "Moderate",
        "low": "Low",
    }
    category_map = {
        "hardware": "Hardware Issue",
        "software": "Software Issue",
        "network": "Network Issue",
        "access": "Software Issue",
        "robotics": "Others",
        "other": "Others",
    }

    for ticket in Ticket.objects.all().iterator():
        ticket.status = status_map.get(ticket.status, "Open")
        ticket.priority = priority_map.get(ticket.priority, "Moderate")
        ticket.category = category_map.get(ticket.category, "Others")
        ticket.created_by_id = ticket.reporter_id
        ticket.save(
            update_fields=["status", "priority", "category", "created_by"]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_department"),
        ("tickets", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="ticket",
            old_name="area",
            new_name="location",
        ),
        migrations.RenameField(
            model_name="ticket",
            old_name="resolution",
            new_name="resolution_notes",
        ),
        migrations.AddField(
            model_name="ticket",
            name="source_ticket_id",
            field=models.CharField(
                blank=True,
                help_text="Original GRTKT ID when imported from Apps Script.",
                max_length=32,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="created_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_tickets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="resolved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resolved_tickets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="downtime_start",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="ticket",
            name="downtime_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="downtime_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="resolution_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="response_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="escalated_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="ticket",
            name="escalated_to",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="ticket",
            name="reopen_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="ticket",
            name="tags",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="root_cause",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Hardware Failure", "Hardware Failure"),
                    ("Software Bug", "Software Bug"),
                    ("User Error", "User Error"),
                    ("Configuration", "Configuration"),
                    ("Network", "Network"),
                    ("Power", "Power"),
                    ("Environmental", "Environmental"),
                    ("Unknown", "Unknown"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="impact_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Critical", "Critical"),
                    ("High", "High"),
                    ("Medium", "Medium"),
                    ("Low", "Low"),
                ],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="affected_stations",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="ticketcomment",
            name="source_comment_id",
            field=models.CharField(
                blank=True,
                max_length=32,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="ticketevent",
            name="source_event_id",
            field=models.CharField(
                blank=True,
                max_length=32,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="ticketevent",
            name="from_status",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="ticketevent",
            name="to_status",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="ticketevent",
            name="note",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="ticket",
            name="category",
            field=models.CharField(
                choices=[
                    ("Hardware Issue", "Hardware Issue"),
                    ("Software Issue", "Software Issue"),
                    ("Network Issue", "Network Issue"),
                    ("Environment Issue", "Environment Issue"),
                    ("Calibration Issue", "Calibration Issue"),
                    ("Data Quality Issue", "Data Quality Issue"),
                    ("Others", "Others"),
                ],
                db_index=True,
                default="Others",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="ticket",
            name="priority",
            field=models.CharField(
                choices=[
                    ("Urgent", "Urgent"),
                    ("High", "High"),
                    ("Moderate", "Moderate"),
                    ("Low", "Low"),
                ],
                db_index=True,
                default="Moderate",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="ticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("Open", "Open"),
                    ("Assigned", "Assigned"),
                    ("In Progress", "In Progress"),
                    ("On Hold", "On Hold"),
                    ("Resolved", "Resolved"),
                    ("Closed", "Closed"),
                    ("Reopened", "Reopened"),
                ],
                db_index=True,
                default="Open",
                max_length=32,
            ),
        ),
        migrations.RunPython(
            convert_existing_tickets,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="ticket",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_tickets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
