import functools
import json
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Type

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.http.response import JsonResponse
from django.views import View
from django_autowired import params
from django_autowired.dependency.models import Dependant
from django_autowired.dependency.utils import DependantUtils
from django_autowired.exceptions import APIException
from django_autowired.exceptions import RequestValidationError
from django_autowired.typing import BodyType
from django_autowired.utils import BodyConverter
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic.error_wrappers import ErrorWrapper
from pydantic.fields import ModelField

ViewFunc = Callable


def _prepare_response_content(
    content: Any,
    *,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
) -> Any:
    if isinstance(content, BaseModel):
        return content.dict(
            by_alias=True,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
    elif isinstance(content, list):
        return [
            _prepare_response_content(
                item,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            )
            for item in content
        ]
    elif isinstance(content, dict):
        return {
            k: _prepare_response_content(
                v,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            )
            for k, v in content.items()
        }
    return content


def serialize_response(
    *,
    response_content: Any,
    field: Optional[ModelField] = None,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    by_alias: bool = True,
) -> Any:
    if field:
        errors = []
        response_content = _prepare_response_content(
            content=response_content,
        )
        value, errors_ = field.validate(response_content, {}, loc=("response",))

        if isinstance(errors_, ErrorWrapper):
            errors.append(errors_)
        elif isinstance(errors_, list):
            errors.extend(errors_)

        if errors:
            raise ValidationError(errors, field.type_)
        result = value.dict(by_alias=by_alias, include=include, exclude=exclude)

        if "__root__" in result:
            result = result["__root__"]

        return result

    else:
        return response_content


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


class Autowired(object):
    def __init__(self) -> None:
        # TODO
        self._view_route: Dict[ViewFunc, ViewRoute] = {}

    def __call__(
        self,
        description: Optional[str] = None,
        dependencies: Optional[List[params.Depends]] = None,
        status_code: int = 200,
        response_model: Optional[Type[Any]] = None,
        response_class: Type[HttpResponse] = JsonResponse,
        response_model_include: Optional[Set[str]] = None,
        response_model_exclude: Optional[Set[str]] = None,
        response_model_by_alias: bool = True,
    ) -> ViewFunc:
        def decorator(func: ViewFunc) -> ViewFunc:
            # TODO
            route = ViewRoute(
                view_func=func,
                dependencies=dependencies,
                status_code=status_code,
                response_model=response_model,
                response_class=response_class,
                response_model_include=response_model_include,
                response_model_exclude=response_model_exclude,
                response_model_by_alias=response_model_by_alias,
            )
            self._view_route[func] = route
            body_field = route.body_field
            is_body_form = route.is_body_form

            def inner(*args, **kwargs) -> Any:
                """
                When called, the method will identify and inject the dependency
                """
                dependant = self._view_route[func].dependant
                view_func = func
                if dependant.ismethod:
                    # class-base view
                    view_self = args[0]
                    view_func = functools.partial(func, view_self)
                    view_request: HttpRequest = args[1]
                    # view_args = args[2:]
                else:
                    # function view
                    view_request = args[0]
                    # view_args = args[1:]
                # slove dependency
                try:
                    body: Optional[BodyType] = None

                    if body_field:
                        if is_body_form:
                            body = BodyConverter.to_form(request=view_request)
                        else:
                            body = BodyConverter.to_json(request=view_request)
                except json.JSONDecodeError as e:
                    raise RequestValidationError(
                        [ErrorWrapper(exc=e, loc=("body", e.pos))], body=e.doc
                    )
                except Exception:
                    raise APIException(detail="parse body error", status_code=422)

                solved_result = dependant.solve_dependencies(
                    request=view_request,
                    body=body,
                    path_kwargs=kwargs,
                    is_body_form=is_body_form,
                )
                values, errors = solved_result
                if errors:
                    # design after
                    raise RequestValidationError(errors=errors, body=body)

                raw_response = view_func(**values)

                if isinstance(raw_response, HttpResponse):
                    return raw_response
                else:
                    response_data = serialize_response(
                        response_content=raw_response,
                        field=route.response_field,
                        include=response_model_include,
                        exclude=response_model_exclude,
                        by_alias=response_model_by_alias,
                    )
                    response = response_class(response_data, status=status_code)
                    return response

            return inner

        return decorator


autowired = Autowired()


class ClassView(View):
    @autowired(description="this is post method")
    def post(self, request, a: int, b: str, c):
        print(self, request, a, b, c)

    # @autowired(description="this is put method")
    def put(self, request):
        pass


@autowired(description="this is func view")
def func_view(request):
    pass


if __name__ == "__main__":
    v = ClassView()
    v.post(1, a=1, b="1", c="1")
