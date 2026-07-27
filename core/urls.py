from django.urls import path

from .views import HealthView, SystemStatusView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("system-status/", SystemStatusView.as_view(), name="system-status"),
]
