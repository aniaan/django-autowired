import inspect
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from django_autowired.dependency.models import Dependant
from pydantic.typing import evaluate_forwardref
from pydantic.typing import ForwardRef


class DependantUtils(object):
    @classmethod
    def get_dependant(cls, call: Callable, name: Optional[str] = None) -> Dependant:
        """Analyzing method parameters to obtain dependencies"""
        signature = cls.get_typed_signature(call=call)
        signature_params: List[inspect.Parameter] = list(signature.parameters.values())

        if not signature_params:
            raise Exception(
                "The django view function must have at least a request argument"
            )

        ismethod = True if signature_params[0].name == "self" else False

        if ismethod:
            # The second paramter must be request
            if len(signature_params) < 2:
                raise Exception(
                    "The django view function is missing a request parameter."
                )
            typed_params = signature_params[2:]
        else:
            # The first paramter must be request
            typed_params = signature_params[1:]

        dependant = Dependant(call=call, ismethod=ismethod)

        for param in typed_params:
            pass

        return dependant

    @classmethod
    def get_typed_signature(cls, call: Callable) -> inspect.Signature:
        signature = inspect.signature(call)
        # call global namespace
        globalns = getattr(call, "__globals__", {})

        typed_params = [
            inspect.Parameter(
                name=param.name,
                kind=param.kind,
                default=param.default,
                annotation=cls.get_typed_annotation(param, globalns),
            )
            for param in signature.parameters.values()
        ]
        typed_signature = inspect.Signature(typed_params)
        return typed_signature

    @classmethod
    def get_typed_annotation(
        cls, param: inspect.Parameter, globalns: Dict[str, Any]
    ) -> Any:
        annotation = param.annotation
        if isinstance(annotation, str):
            # Ref: https://github.com/samuelcolvin/pydantic/issues/1738
            annotation = ForwardRef(annotation)  # type: ignore
            annotation = evaluate_forwardref(annotation, globalns, globalns)
        return annotation
