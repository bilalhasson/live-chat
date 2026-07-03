from django.contrib import admin
from django.urls import path

from chat import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.demo, name="demo"),
    path("healthz", views.healthz, name="healthz"),
    path("widget.js", views.widget_js, name="widget_js"),
]
