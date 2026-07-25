from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_department"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("agent", "Agent"),
                    ("team", "Tech Team / TL / Manager"),
                    ("system_admin", "System administrator"),
                ],
                db_index=True,
                default="agent",
                max_length=32,
            ),
        ),
    ]
