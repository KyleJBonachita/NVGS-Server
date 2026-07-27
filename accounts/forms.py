from django import forms
from django.contrib.auth.password_validation import (
    password_validators_help_text_html,
    validate_password,
)
from django.core.exceptions import ValidationError

from .models import User


class SsoOnboardingForm(forms.Form):
    first_name = forms.CharField(
        label="First name",
        max_length=User._meta.get_field("first_name").max_length,
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=User._meta.get_field("last_name").max_length,
    )
    password1 = forms.CharField(
        label="Create an NVGS password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Confirm NVGS password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, user: User, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords did not match.")
        if password1:
            try:
                validate_password(password1, self.user)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned_data

    def save(self) -> User:
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.set_password(self.cleaned_data["password1"])
        self.user.full_clean()
        self.user.save(
            update_fields=[
                "first_name",
                "last_name",
                "password",
            ]
        )
        return self.user
