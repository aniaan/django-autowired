from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

from django.views import View

ViewFunc = Callable


class Autowired(object):
    def __init__(self) -> None:
        # TODO
        self._view_dependant: Dict[ViewFunc, Any] = {}

    def __call__(self, description: Optional[str] = None) -> ViewFunc:
        def decorator(func: ViewFunc) -> ViewFunc:
            # TODO
            self._view_dependant[func] = None

            def inner(*args, **kwargs) -> Any:
                """
                When called, the method will identify and inject the dependency
                """
                # identify
                # inject
                return func(*args, **kwargs)

            return inner

        return decorator


autowired = Autowired()


class ClassView(View):
    @autowired(description="this is post method")
    def post(self, request):
        pass

    # @autowired(description="this is put method")
    def put(self, request):
        pass


# @autowired(description="this is func view")
def func_view(request):
    pass


if __name__ == "__main__":
    v = ClassView()
    v.post(1)
    # print(v.put)
