from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from chat import dashboard, views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Public
    path("", views.demo, name="demo"),
    path("healthz", views.healthz, name="healthz"),
    path("widget.js", views.widget_js, name="widget_js"),
    path("widget/<str:site_key>/config.json", views.widget_config, name="widget_config"),

    # Auth
    path("signup/", dashboard.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Dashboard (login required)
    path("sites/", dashboard.sites, name="sites"),
    path("sites/<int:pk>/", dashboard.site_detail, name="site_detail"),
    path("sites/<int:pk>/delete/", dashboard.site_delete, name="site_delete"),
    path("inbox/", dashboard.inbox, name="inbox"),
]
