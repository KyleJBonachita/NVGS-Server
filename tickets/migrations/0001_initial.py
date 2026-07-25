import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('description', models.TextField()),
                ('category', models.CharField(choices=[('hardware', 'Hardware'), ('software', 'Software'), ('network', 'Network'), ('access', 'Account or access'), ('robotics', 'Robotics'), ('other', 'Other')], db_index=True, default='other', max_length=32)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], db_index=True, default='normal', max_length=16)),
                ('status', models.CharField(choices=[('new', 'New'), ('acknowledged', 'Acknowledged'), ('assigned', 'Assigned'), ('in_progress', 'In progress'), ('waiting_for_agent', 'Waiting for agent'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('cancelled', 'Cancelled')], db_index=True, default='new', max_length=32)),
                ('area', models.CharField(blank=True, max_length=120)),
                ('workstation', models.CharField(blank=True, max_length=120)),
                ('resolution', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tickets', to=settings.AUTH_USER_MODEL)),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reported_tickets', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('is_internal', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ticket_comments', to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='tickets.ticket')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=64)),
                ('changes', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ticket_events', to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='tickets.ticket')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['status', '-created_at'], name='tickets_tic_status_15eec8_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['assignee', 'status'], name='tickets_tic_assigne_294cb9_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['reporter', '-created_at'], name='tickets_tic_reporte_45e934_idx'),
        ),
    ]
