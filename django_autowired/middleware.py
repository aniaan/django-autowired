from typing import Optional

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.http.response import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django_autowired.exceptions import APIException
from django_autowired.exceptions import RequestValidationError


class AutoWiredExceptionMiddleware(MiddlewareMixin):
    def process_exception(
        self, request: HttpRequest, exc: Exception
    ) -> Optional[HttpResponse]:
        if isinstance(exc, APIException):
            return JsonResponse(status=exc.status_code, data={"detail": exc.detail})
        elif isinstance(exc, RequestValidationError):
            return JsonResponse(status=400, data={"detail": str(exc)})
        else:
            raise exc
