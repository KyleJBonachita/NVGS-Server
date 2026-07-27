from django.urls import path

from .views import (
    AssignableUserListView,
    CsrfView,
    CurrentUserView,
    LoginView,
    LogoutView,
    UserListView,
    appscript_sso_callback,
    appscript_sso_consume,
    appscript_sso_onboarding,
    appscript_sso_start,
)

urlpatterns = [
    path(
        "appscript/start/",
        appscript_sso_start,
        name="appscript-sso-start",
    ),
    path(
        "appscript/consume/",
        appscript_sso_consume,
        name="appscript-sso-consume",
    ),
    path(
        "appscript/callback/",
        appscript_sso_callback,
        name="appscript-sso-callback",
    ),
    path(
        "appscript/onboarding/",
        appscript_sso_onboarding,
        name="appscript-sso-onboarding",
    ),
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("users/", UserListView.as_view(), name="user-list"),
    path(
        "users/assignable/",
        AssignableUserListView.as_view(),
        name="assignable-user-list",
    ),
]
