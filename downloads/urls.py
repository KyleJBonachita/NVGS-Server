from django.urls import path

from .views import download_manager

urlpatterns = [
    path("manage/", download_manager, name="download-manager"),
]
