from django.contrib import admin
from django.urls import include, path

from accounts.web_views import home, login_page
from tickets.web_views import dashboard

urlpatterns = [
    path("", home, name="home"),
    path("login/", login_page, name="login-page"),
    path("tickets/", dashboard, name="ticket-dashboard"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/tickets/", include("tickets.urls")),
]
