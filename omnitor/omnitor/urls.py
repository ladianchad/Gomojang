from django.urls import path
from .views.pages.dashboard import sensor_dashboard_view
from .views.apis import urlpatterns as api

urlpatterns = [
   *api
]
