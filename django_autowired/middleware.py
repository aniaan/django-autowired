from typing import Optional

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.http.response import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django_autowired.exceptions import APIException
from django_autowired.exceptions import RequestValidationError


class AutoWiredExceptionMiddleware(MiddlewareMixin):
    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> Optional[HttpResponse]:
        if isinstance(exception, APIException):
            return JsonResponse(
                status=exception.status_code, data={"detail": exception.detail}
            )
        elif isinstance(exception, RequestValidationError):
            return JsonResponse(status=400, data={"detail": "validate params error"})
        else:
            raise exception
