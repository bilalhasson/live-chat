from django.urls import re_path

from chat import consumers

websocket_urlpatterns = [
    re_path(r"^ws/visitor/$", consumers.VisitorConsumer.as_asgi()),
    re_path(r"^ws/operator/$", consumers.OperatorConsumer.as_asgi()),
]
