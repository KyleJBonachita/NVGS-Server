from django.urls import path

from .views import (
    AssignableUserListView,
    CsrfView,
    CurrentUserView,
    LoginView,
    LogoutView,
    UserListView,
)

urlpatterns = [
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
