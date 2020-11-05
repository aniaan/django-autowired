import inspect
from typing import Callable
from typing import Optional

from django_autowired.dependency.models import Dependant


class DependantUtils(object):
    @classmethod
    def get_dependant(cls, call: Callable, name: Optional[str] = None) -> Dependant:
        """Analyzing method parameters to obtain dependencies"""
        pass

    @classmethod
    def get_typed_signature(cls, call: Callable) -> inspect.Signature:
        signature = inspect.signature(call)
        # call global namespace
        # globalns = getattr(call, "__globals__", {})
        # typed_params
        # inspect.Parameter
        # typed_params: List[inspect.Parameter] = []

        # for param in signature.parameters.values():
        # pass

        return signature
