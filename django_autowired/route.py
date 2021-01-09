import re
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Pattern
from typing import Set
from typing import Tuple
from typing import Type

from django.http.response import HttpResponse
from django.http.response import JsonResponse
from django_autowired import params
from django_autowired.dependency.models import Dependant
from django_autowired.dependency.utils import DependantUtils
from django_autowired.openapi.convertors import Convertor
from django_autowired.openapi.convertors import CONVERTOR_TYPES
from django_autowired.utils import get_view_name
from pydantic.fields import ModelField

ViewFunc = Callable

# Match parameters in URL paths, eg.
PARAM_REGEX = re.compile("<([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?>")


def compile_path(
    path: str,
) -> Tuple[Pattern[str], str, Dict[str, Convertor]]:
    """
    Given a path string, like: "/<username:str>", return a three-tuple
    of (regex, format, {param_name:convertor}).

    regex:      "/(?P<username>[^/]+)"
    format:     "/{username}"
    convertors: {"username": StringConvertor()}
    """
    path_regex = "^"
    path_format = ""

    idx = 0
    param_convertors = {}
    for match in PARAM_REGEX.finditer(path):
        param_name, convertor_type = match.groups("str")
        convertor_type = convertor_type.lstrip(":")
        assert (
            convertor_type in CONVERTOR_TYPES
        ), f"Unknown path convertor '{convertor_type}'"
        convertor = CONVERTOR_TYPES[convertor_type]

        path_regex += re.escape(path[idx : match.start()])
        path_regex += f"(?P<{param_name}>{convertor.regex})"

        path_format += path[idx : match.start()]
        path_format += "{%s}" % param_name

        param_convertors[param_name] = convertor

        idx = match.end()

    path_regex += re.escape(path[idx:]) + "$"
    path_format += path[idx:]
    return re.compile(path_regex), path_format, param_convertors


class ViewRoute(object):
    def __init__(
        self,
        view_func: ViewFunc,
        status_code: int = 200,
        dependencies: Optional[List[params.Depends]] = None,
        response_model: Optional[Type[Any]] = None,
        response_class: Optional[Type[HttpResponse]] = None,
        response_model_include: Optional[Set[str]] = None,
        response_model_exclude: Optional[Set[str]] = None,
        response_model_by_alias: bool = True,
        include_in_schema: bool = True,
        tags: Optional[List[str]] = None,
        deprecated: Optional[bool] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        name: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> None:
        self._view_func = view_func
        self._dependencies = dependencies or []
        self._dependant = Dependant.new_dependant(call=view_func, is_view_func=True)
        for depends in self._dependencies[::-1]:
            self._dependant.dependencies.insert(
                0,
                self._dependant.new_paramless_sub_dependant(depends=depends),
            )
        self._unique_id = str(view_func)
        self._body_field = self._dependant.get_body_field(name=self._unique_id)
        self._is_body_form = bool(
            self._body_field and isinstance(self._body_field.field_info, params.Form)
        )
        self._response_model = response_model
        self._response_class = response_class or JsonResponse

        if self._response_model:
            response_name = "Response_" + self._unique_id
            self._response_field = DependantUtils.create_model_field(
                name=response_name, type_=self._response_model
            )
            self._cloned_response_field = DependantUtils.create_cloned_field(
                field=self._response_field,
            )
        else:
            self._response_field = None
            self._cloned_response_field = None

        self._status_code = status_code

        self.tags: List[str] = tags or []
        self.deprecated = deprecated
        self.include_in_schema = include_in_schema
        self.summary = summary
        self.description = description
        self.response_description = response_description
        self.name = name if name else get_view_name(view_func)
        self.operation_id = operation_id
        self.qualname = self._view_func.__qualname__
        self.methods = [self._view_func.__name__.upper()]
        self.set_path(path="")

    def set_path(self, path: str) -> None:
        self.path = path
        self.path_regex, self.path_format, self.param_convertors = compile_path(
            self.path
        )

    @property
    def dependant(self) -> Dependant:
        return self._dependant

    @property
    def is_body_form(self) -> bool:
        return self._is_body_form

    @property
    def body_field(self) -> Optional[ModelField]:
        return self._body_field

    @property
    def response_field(self) -> Optional[ModelField]:
        return self._cloned_response_field

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def response_class(self) -> Optional[Type[HttpResponse]]:
        return self._response_class
