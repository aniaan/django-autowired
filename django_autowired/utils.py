import inspect
import json

from django.http.request import HttpRequest
from django.utils.datastructures import MultiValueDict
from django_autowired.typing import JSON
from django_autowired.typing import ViewFunc


def get_view_name(view_func: ViewFunc) -> str:
    if inspect.isfunction(view_func) or inspect.isclass(view_func):
        return view_func.__name__

    return view_func.__class__.__name__


def get_body_form(request: HttpRequest):
    pass


def get_body_json(request: HttpRequest) -> JSON:
    body_bytes = request.body
    body = None
    if body_bytes:
        body = json.loads(body_bytes)
    return body


class BodyConverter(object):
    @classmethod
    def to_form(cls, request: HttpRequest) -> MultiValueDict:
        data = MultiValueDict()
        data.update(request.POST)
        data.update(request.FILES)

        return data

    @classmethod
    def to_json(cls, request: HttpRequest) -> JSON:
        body_bytes = request.body
        body = None
        if body_bytes:
            body = json.loads(body_bytes)
        return body
