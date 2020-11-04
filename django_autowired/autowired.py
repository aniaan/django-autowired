from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

ViewFunc = Callable


class Autowired(object):
    def __init__(self) -> None:
        # TODO
        self._view_dependant: Dict[ViewFunc, Any] = {}

    def __call__(self, description: Optional[str] = None) -> ViewFunc:
        def decorator(func: ViewFunc) -> ViewFunc:
            # TODO
            self._view_dependant[func] = None

            def inner() -> Any:
                """
                When called, the method will identify and inject the dependency
                """
                # identify
                # inject
                return func()

            return inner

        return decorator


autowired = Autowired()


class View(object):
    @autowired(description="this is post method")
    def post(self, request):
        pass

    @autowired(description="this is put method")
    def put(self, request):
        pass
