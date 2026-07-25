from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .managers import UserManager


class UserRole(models.TextChoices):
    AGENT = "agent", "Agent"
    TEAM = "team", "Tech Team / TL / Manager"
    SYSTEM_ADMIN = "system_admin", "System administrator"


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.AGENT,
        db_index=True,
    )
    department = models.CharField(max_length=120, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        domain = self.email.rsplit("@", 1)[-1] if "@" in self.email else ""
        if settings.ALLOWED_EMAIL_DOMAINS and domain not in settings.ALLOWED_EMAIL_DOMAINS:
            allowed = ", ".join(settings.ALLOWED_EMAIL_DOMAINS)
            raise ValidationError(
                {"email": f"Email must belong to an approved domain: {allowed}."}
            )

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email).lower()
        if self.role == UserRole.SYSTEM_ADMIN or self.is_superuser:
            self.is_staff = True
        elif self.role != UserRole.SYSTEM_ADMIN:
            self.is_staff = False
        super().save(*args, **kwargs)

    @property
    def can_manage_tickets(self) -> bool:
        return self.role in {UserRole.TEAM, UserRole.SYSTEM_ADMIN}

    @property
    def display_name(self) -> str:
        return self.get_full_name().strip() or self.email

    def __str__(self):
        return self.display_name
