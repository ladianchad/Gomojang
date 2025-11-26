from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def sensor_dashboard_view(request: HttpRequest) -> HttpResponse:
    return render(request, "omnitor/index.html")