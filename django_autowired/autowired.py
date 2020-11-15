from django_autowired.utils import BodyConverter
import functools
import json
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from django.http.request import HttpRequest
from django.views import View
from django_autowired import params
from django_autowired.dependency.models import Dependant
from django_autowired.typing import BodyType

ViewFunc = Callable


class ViewRoute(object):
    def __init__(
        self,
        view_func: ViewFunc,
        dependencies: Optional[List[params.Depends]] = None,
    ) -> None:
        self.view_func = view_func
        self.dependencies = dependencies or []
        self.dependant = Dependant.new_dependant(call=view_func, is_view_func=True)
        for depends in self.dependencies[::-1]:
            self.dependant.dependencies.insert(
                0,
                self.dependant.new_paramless_sub_dependant(depends=depends),
            )
        self.unique_id = str(view_func)
        self.body_field = self.dependant.get_body_field(name=self.unique_id)
        self.is_body_form = self.body_field and isinstance(
            self.body_field.field_info, params.Form
        )


class Autowired(object):
    def __init__(self) -> None:
        # TODO
        self._view_route: Dict[ViewFunc, ViewRoute] = {}

    def __call__(
        self,
        description: Optional[str] = None,
        dependencies: Optional[List[params.Depends]] = None,
    ) -> ViewFunc:
        def decorator(func: ViewFunc) -> ViewFunc:
            # TODO
            route = ViewRoute(view_func=func, dependencies=dependencies)
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
                    view_args = args[2:]
                else:
                    # function view
                    view_request = args[0]
                    view_args = args[1:]
                # slove dependency
                try:
                    body: Optional[BodyType] = None
                    if body_field:
                        if is_body_form:
                            body = BodyConverter.to_form(request=view_request)
                        else:
                            body = BodyConverter.to_json(request=view_request)
                except json.JSONDecodeError:
                    raise Exception("body json dencode error")
                except Exception:
                    raise Exception("parse body error")

                # inject
                return view_func(view_request, body, *view_args, **kwargs)

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
    # print(v.put)
