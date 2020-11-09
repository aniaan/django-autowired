import inspect
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Optional
from typing import Type

from django.http.request import HttpRequest
from django_autowired import params
from django_autowired.dependency.utils import DependantUtils
from pydantic import create_model
from pydantic.fields import ModelField


class Dependant(object):
    def __init__(
        self,
        *,
        call: Optional[Callable] = None,
        ismethod: bool = False,
        is_view_func: bool = False,
        name: Optional[str] = None,
        parent_dependant: Optional["Dependant"] = None,
        path_params: Optional[List[ModelField]] = None,
        query_params: Optional[List[ModelField]] = None,
        header_params: Optional[List[ModelField]] = None,
        cookie_params: Optional[List[ModelField]] = None,
        body_params: Optional[List[ModelField]] = None,
    ) -> None:
        self.call = call
        self.ismethod = ismethod
        self.is_view_func = is_view_func
        self.name = name

        self.parent_dependant = parent_dependant
        self.path_params: List[ModelField] = path_params or []
        self.query_params: List[ModelField] = query_params or []
        self.header_params: List[ModelField] = header_params or []
        self.cookie_params: List[ModelField] = cookie_params or []
        self.body_params: List[ModelField] = body_params or []
        self.dependencies: List[Dependant] = []

        self.request_param_name: Optional[str] = None

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

    def add_special_param_field(self, param: inspect.Parameter) -> bool:
        """Add special param, such as requset"""
        if isinstance(param.annotation, HttpRequest) or param.name == "request":
            self.request_param_name = param.name
            return True

        return False

    @classmethod
    def new_dependant(
        cls,
        call: Callable,
        name: Optional[str] = None,
        parent_dependant: Optional["Dependant"] = None,
        is_view_func: bool = False,
    ) -> "Dependant":
        """Analyzing method parameters to obtain dependencies"""
        signature = DependantUtils.get_typed_signature(call=call)
        signature_params: List[inspect.Parameter] = list(signature.parameters.values())

        if not signature_params:
            raise Exception(
                "The django view function must have at least a request argument"
            )

        ismethod = True if signature_params[0].name == "self" else False

        if is_view_func and ismethod and len(signature_params) < 2:
            raise Exception("The django view function is missing a request parameter.")

        dependant = Dependant(
            call=call,
            ismethod=ismethod,
            name=name,
            parent_dependant=parent_dependant,
            is_view_func=is_view_func,
        )

        typed_params = signature_params

        for param in typed_params:

            if param.name == "self":
                continue

            if isinstance(param.default, params.Depends):
                sub_dependant = dependant.new_param_sub_dependant(param=param)
                dependant.dependencies.append(sub_dependant)
                continue

            if dependant.add_special_param_field(param=param):
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

    def flat(self) -> "Dependant":
        """Flatten all params"""
        flat_dependant = Dependant(
            path_params=self.path_params.copy(),
            query_params=self.query_params.copy(),
            header_params=self.header_params.copy(),
            cookie_params=self.cookie_params.copy(),
            body_params=self.body_params.copy(),
        )

        for sub_dependency in self.dependencies:
            sub_dependant = sub_dependency.flat()

            flat_dependant.path_params.extend(sub_dependant.path_params)
            flat_dependant.query_params.extend(sub_dependant.query_params)
            flat_dependant.header_params.extend(sub_dependant.header_params)
            flat_dependant.cookie_params.extend(sub_dependant.cookie_params)
            flat_dependant.body_params.extend(sub_dependant.body_params)

        return flat_dependant

    def get_body_field(self, *, name: str) -> Optional[ModelField]:
        """
        name: must be unique
        """
        flat_dependant = self.flat()

        if not flat_dependant.body_params:
            return None

        first_param = flat_dependant.body_params[0]
        first_param_embed = getattr(first_param, "embed", False)
        param_name_set = {param.name for param in flat_dependant.body_params}

        if len(param_name_set) == 1 and not first_param_embed:
            return first_param

        for param in flat_dependant.body_params:
            setattr(param.field_info, "embed", True)

        model_name = "Body_" + name
        BodyModel = create_model(model_name)

        for param in flat_dependant.body_params:
            BodyModel.__fields__[param.name] = param

        required = any(True for f in flat_dependant.body_params if f.required)

        BodyFieldInfo_kwargs: Dict[str, Any] = dict(default=None)
        if any(
            isinstance(param.field_info, params.File)
            for param in flat_dependant.body_params
        ):
            BodyFieldInfo: Type[params.Body] = params.File
        elif any(
            isinstance(f.field_info, params.Form) for f in flat_dependant.body_params
        ):
            BodyFieldInfo = params.Form
        else:
            BodyFieldInfo = params.Body

            body_param_media_types = [
                getattr(f.field_info, "media_type")
                for f in flat_dependant.body_params
                if isinstance(f.field_info, params.Body)
            ]
            if len(set(body_param_media_types)) == 1:
                BodyFieldInfo_kwargs["media_type"] = body_param_media_types[0]
        final_field = DependantUtils.create_model_field(
            name="body",
            type_=BodyModel,
            required=required,
            alias="body",
            field_info=BodyFieldInfo(**BodyFieldInfo_kwargs),
        )

        return final_field

    def solve_dependencies(self, *, request: HttpRequest, path_kwargs: Dict[str, Any]):
        pass
