from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.urls import path

def api_setting(request):
    handlers = {
        "GET": get_handler
    }

    handler = handlers.get(request.method)
    if handler is None:
        return HttpResponseBadRequest("Only POST requests are allowed.")

    return handler(request)

api_path = path('calibration_api/', api_setting, name='calibration_api')

def get_handler(request: HttpRequest) -> HttpResponse:
    return render(request, "omnitor/index.html")
