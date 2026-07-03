from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from chat import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.demo, name="demo"),
    path("healthz", views.healthz, name="healthz"),
    path("widget.js", views.widget_js, name="widget_js"),
    path("operator/", views.operator_dashboard, name="operator"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
