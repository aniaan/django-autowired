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
from django_autowired.exceptions import APIException
from django_autowired.exceptions import RequestValidationError
from django_autowired.openapi.docs import get_swagger_ui_html
from django_autowired.openapi.utils import OpenAPISchemaGenerator
from django_autowired.route import ViewRoute
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


class Autowired(object):
    def __init__(self) -> None:
        # TODO
        self._view_route: Dict[ViewFunc, ViewRoute] = {}

    def setup_schema(
        self,
        title: str = "test",
        description: str = "测试",
        version: str = "0.1.0",
    ):
        self.title = title
        self.description = description
        self.version = version
        self.openapi_version = "3.0.2"
        self.openapi_url = "/openapi.json"

        assert self.title, "A title must be provided for OpenAPI, e.g.: 'My API'"
        assert self.version, "A version must be provided for OpenAPI, e.g.: '2.1.0'"

        self.openapi_schema: Optional[Dict[str, Any]] = None
        self.setup()

    @property
    def view_route(self) -> Dict[ViewFunc, ViewRoute]:
        return self._view_route

    def setup(self):
        self.setup_openapi_view()
        self.setup_swagger_ui_view()

    def get_openapi_view(self) -> ViewFunc:
        return self.openapi_view

    def get_swagger_ui_view(self) -> ViewFunc:
        return self.swagger_view

    def openapi(self) -> Dict:
        if not self.openapi_schema:
            generator = OpenAPISchemaGenerator(
                title=self.title,
                version=self.version,
                openapi_version=self.openapi_version,
                description=self.description,
                view_route=self._view_route,
            )
            self.openapi_schema = generator.get_schema()
        return self.openapi_schema

    def setup_openapi_view(self) -> None:
        func = self.openapi

        def openapiView(request):
            return JsonResponse(func())

        self.openapi_view = openapiView

    def setup_swagger_ui_view(self) -> None:
        openapi_url = self.openapi_url
        title = self.title + " - Swagger UI"

        def swaggerView(request):
            return get_swagger_ui_html(
                openapi_url=openapi_url,
                title=title,
            )

        self.swagger_view = swaggerView

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
        include_in_schema: bool = True,
        tags: Optional[List[str]] = None,
        deprecated: Optional[bool] = None,
        summary: Optional[str] = None,
        response_description: str = "Successful Response",
        name: Optional[str] = None,
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
                include_in_schema=include_in_schema,
                tags=tags,
                deprecated=deprecated,
                summary=summary,
                response_description=response_description,
                name=name,
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
