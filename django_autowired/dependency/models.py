import inspect
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Optional

from django.http.request import HttpRequest
from django_autowired import params
from django_autowired.dependency.utils import DependantUtils
from pydantic.fields import ModelField


class Dependant(object):
    def __init__(
        self,
        *,
        call: Callable,
        ismethod: bool = True,
        name: Optional[str] = None,
        parent_dependant: Optional["Dependant"] = None,
    ) -> None:
        self.call = call
        self.ismethod = ismethod
        self.name = name

        self.parent_dependant = parent_dependant
        self.path_params: List[ModelField] = []
        self.query_params: List[ModelField] = []
        self.header_params: List[ModelField] = []
        self.cookie_params: List[ModelField] = []
        self.body_params: List[ModelField] = []
        self.dependencies: List[Dependant] = []

    def add_param_field(
        self, param: inspect.Parameter, param_field: ModelField
    ) -> None:
        if DependantUtils.is_scalar_field(field=param_field):
            self._add_scalar_field(param_field=param_field)
        elif isinstance(
            param.default, (params.Query, params.Header)
        ) and DependantUtils.is_scalar_sequence_field(field=param_field):
            self._add_scalar_field(param_field=param_field)
        else:
            self._add_body_field(param_field=param_field)

    def _add_scalar_field(self, param_field: ModelField) -> None:
        """Add param_field to path or query or header or cookie params"""
        field_info = cast(params.Param, param_field.field_info)

        if field_info.in_ == params.ParamTypes.path:
            self.path_params.append(param_field)
        elif field_info.in_ == params.ParamTypes.query:
            self.query_params.append(param_field)
        elif field_info.in_ == params.ParamTypes.header:
            self.header_params.append(param_field)
        elif field_info.in_ == params.ParamTypes.cookie:
            self.cookie_params.append(param_field)
        else:
            raise Exception(
                f"non-body parameters must be in "
                f"path, query, header or cookie: {param_field.name}"
            )

    def _add_body_field(self, param_field: ModelField) -> None:
        if isinstance(param_field.field_info, params.Body):
            raise Exception(
                f"Param: {param_field.name} can only be a request body, using Body(...)"
            )
        self.body_params.append(param_field)

    @classmethod
    def new_dependant(
        cls,
        call: Callable,
        name: Optional[str] = None,
        parent_dependant: Optional["Dependant"] = None,
    ) -> "Dependant":
        """Analyzing method parameters to obtain dependencies"""
        signature = DependantUtils.get_typed_signature(call=call)
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

        dependant = Dependant(
            call=call, ismethod=ismethod, name=name, parent_dependant=parent_dependant
        )

        for param in typed_params:
            if isinstance(param.default, params.Depends):
                sub_dependant = dependant.new_param_sub_dependant(param=param)
                dependant.dependencies.append(sub_dependant)
                continue
            param_field = DependantUtils.get_param_field(
                param=param, default_field_info_class=params.Query
            )
            # There's no way to know if the param exists in the path or not.
            dependant.add_param_field(param=param, param_field=param_field)

        return dependant

    def new_param_sub_dependant(self, param: inspect.Parameter) -> "Dependant":
        depends: params.Depends = param.default

        if not isinstance(depends, params.Depends):
            raise Exception("sub-dependant type must be Depends")

        dependency = depends.dependency if depends.dependency else param.annotation
        return self._new_sub_dependant(depends=depends, dependency=dependency)

    def new_paramless_sub_dependant(self, depends: params.Depends) -> "Dependant":
        if not callable(depends.dependency):
            raise Exception("dependency must be callable")
        return self._new_sub_dependant(depends=depends, dependency=depends.dependency)

    def _new_sub_dependant(
        self, depends: params.Depends, dependency: Callable, name: Optional[str] = None
    ) -> "Dependant":
        sub_dependant = self.new_dependant(
            call=dependency, name=name, parent_dependant=self
        )
        return sub_dependant

    def solve_dependencies(self, *, request: HttpRequest, path_kwargs: Dict[str, Any]):
        pass
