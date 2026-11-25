from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", views.complaint, name="complaint"),
    path("employee/login/", views.PortalLogin.as_view(), name="employee-login"),
    path("admin/login/", views.PortalLogin.as_view(admin_portal=True), name="admin-login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("desk/", views.queue, name="queue"),
    path("desk/<int:pk>/", views.ticket_detail, name="ticket"),
    path("accounts/login/", RedirectView.as_view(pattern_name="admin-login")),
    path("accounts/", admin.site.urls),
]
