from copy import deepcopy
import functools
import inspect
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from django.http.request import QueryDict
from django.utils.datastructures import MultiValueDict
from django_autowired import params
from django_autowired.params import Body
from django_autowired.params import Param
from django_autowired.typing import BodyType
from pydantic import BaseConfig
from pydantic import BaseModel
from pydantic.class_validators import Validator
from pydantic.error_wrappers import ErrorWrapper
from pydantic.errors import MissingError
from pydantic.fields import FieldInfo
from pydantic.fields import ModelField
from pydantic.fields import Required
from pydantic.fields import SHAPE_LIST
from pydantic.fields import SHAPE_SEQUENCE
from pydantic.fields import SHAPE_SET
from pydantic.fields import SHAPE_SINGLETON
from pydantic.fields import SHAPE_TUPLE
from pydantic.fields import SHAPE_TUPLE_ELLIPSIS
from pydantic.fields import UndefinedType
from pydantic.schema import get_annotation_from_field_info
from pydantic.typing import evaluate_forwardref
from pydantic.typing import ForwardRef
from pydantic.utils import lenient_issubclass

SEQUENCE_TYPES = (list, set, tuple)
SEQUENCE_SHAPES = {
    SHAPE_LIST,
    SHAPE_SET,
    SHAPE_TUPLE,
    SHAPE_SEQUENCE,
    SHAPE_TUPLE_ELLIPSIS,
}


def get_missing_field_error(loc: Tuple[str, ...]) -> ErrorWrapper:
    missing_field_error = ErrorWrapper(MissingError(), loc=loc)
    return missing_field_error


class DependantUtils(object):
    @classmethod
    def get_param_field(
        cls, *, param: inspect.Parameter, default_field_info_class: Type[Param] = Param
    ) -> ModelField:
        """Wrapper param to pydantic ModelField"""
        default_value = Required
        had_schema = False
        if param.default != param.empty:
            default_value = param.default

        # wrapper default_value to spec param
        if isinstance(default_value, FieldInfo):
            had_schema = True
            field_info = default_value
            default_value = field_info.default
            if (
                isinstance(field_info, Param)
                and getattr(field_info, "in_", None) is None
            ):
                field_info.in_ = default_field_info_class.in_
        else:
            field_info = default_field_info_class(default_value)

        required = default_value == Required
        annotation: Any = Any
        if not param.annotation == param.empty:
            annotation = param.annotation

        annotation = get_annotation_from_field_info(annotation, field_info, param.name)

        if not field_info.alias and getattr(field_info, "convert_underscores", None):
            # header
            alias = param.name.replace("_", "-")
        else:
            alias = field_info.alias or param.name

        field = cls.create_model_field(
            name=param.name,
            type_=annotation,
            default=None if required else default_value,
            alias=alias,
            required=required,
            field_info=field_info,
        )

        if not had_schema and not cls.is_scalar_field(field=field):
            field.field_info = Body(field_info.default)

        return field

    @classmethod
    def is_scalar_field(cls, field: ModelField) -> bool:
        field_info = field.field_info
        if (
            field.shape != SHAPE_SINGLETON
            or lenient_issubclass(field.type_, BaseModel)
            or lenient_issubclass(field.type_, SEQUENCE_TYPES + (dict,))
            or isinstance(field_info, Body)
        ):
            return False

        if field.sub_fields:
            if not all(cls.is_scalar_field(f) for f in field.sub_fields):
                return False
        return True

    @classmethod
    def is_scalar_sequence_field(cls, field: ModelField) -> bool:
        if (field.shape in SEQUENCE_SHAPES) and not lenient_issubclass(
            field.type_, BaseModel
        ):
            if field.sub_fields is not None:
                for sub_field in field.sub_fields:
                    if not cls.is_scalar_field(sub_field):
                        return False
            return True
        if lenient_issubclass(field.type_, SEQUENCE_TYPES):
            return True
        return False

    @classmethod
    def create_model_field(
        cls,
        *,
        name: str,
        type_: Type[Any],
        class_validators: Optional[Dict[str, Validator]] = None,
        default: Optional[Any] = None,
        required: Union[bool, UndefinedType] = False,
        model_config: Type[BaseConfig] = BaseConfig,
        field_info: Optional[FieldInfo] = None,
        alias: Optional[str] = None,
    ) -> ModelField:
        """
        Create a new response field. Raises if type_ is invalid.
        """
        class_validators = class_validators or {}
        field_info = field_info or FieldInfo(None)

        response_field = functools.partial(
            ModelField,
            name=name,
            type_=type_,
            class_validators=class_validators,
            default=default,
            required=required,
            model_config=model_config,
            alias=alias,
        )

        try:
            return response_field(field_info=field_info)
        except RuntimeError:
            raise Exception(
                "Invalid args for response field!"
                f"Hint: check that {type_} is a valid pydantic field type"
            )

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


class RequestConverter(object):
    @classmethod
    def to_args(
        cls,
        param_fields: List[ModelField],
        param_values: Union[Dict[str, Any], QueryDict, MultiValueDict],
    ) -> Tuple[Dict[str, Any], List[ErrorWrapper]]:
        values: Dict[str, Any] = {}
        errors = []
        for field in param_fields:
            if DependantUtils.is_scalar_sequence_field(field=field) and isinstance(
                param_values, QueryDict
            ):
                value = param_values.getlist(key=field.alias) or field.default
            else:
                value = param_values.get(field.alias)

            field_info = field.field_info

            assert isinstance(
                field_info, params.Param
            ), "Param must be subclasses of Param"

            if value is None:
                if field.required:
                    errors.append(
                        ErrorWrapper(
                            MissingError(), loc=(field_info.in_.value, field.alias)
                        )
                    )
                    continue
                else:
                    # values[field.name] = deepcopy(field.default)
                    value = deepcopy(field.default)

            validate_value, validate_errors = field.validate(
                v=value, values=values, loc=(field_info.in_.value, field.alias)
            )

            if isinstance(validate_errors, ErrorWrapper):
                errors.append(validate_errors)
            elif isinstance(validate_errors, list):
                errors.extend(validate_errors)
            else:
                values[field.name] = validate_value

        return values, errors

    @classmethod
    def to_body(
        cls,
        param_fields: List[ModelField],
        body: Optional[BodyType],
        is_body_form: bool = False,
    ) -> Tuple[Dict[str, Any], List[ErrorWrapper]]:
        values = {}
        errors = []

        if param_fields:
            field = param_fields[0]
            field_info = field.field_info
            embed = getattr(field_info, "embed", False)
            field_alias_omitted = len(param_fields) == 1 and not embed

            if field_alias_omitted:
                body = {field.alias: body}

            for field in param_fields:
                field_info = field.field_info
                loc: Tuple[str, ...]
                if field_alias_omitted:
                    loc = ("body",)
                else:
                    loc = ("body", field.alias)

                value: Optional[Any] = None

                if body is not None:
                    if (
                        field.shape in SEQUENCE_SHAPES or field.type_ in SEQUENCE_TYPES
                    ) and isinstance(body, MultiValueDict):
                        value = body.getlist(field.alias)
                    else:
                        try:
                            value = body.get(field.alias)
                        except AttributeError:
                            errors.append(get_missing_field_error(loc))
                            continue

                if not value:
                    if field.required:
                        errors.append(get_missing_field_error(loc=loc))
                    else:
                        values[field.name] = deepcopy(field.default)

                validate_value, validate_errors = field.validate(
                    v=value, values=values, loc=loc
                )

                if isinstance(validate_errors, ErrorWrapper):
                    errors.append(validate_errors)
                elif isinstance(errors, list):
                    errors.extend(validate_errors)
                else:
                    values[field.name] = validate_value

        return values, errors
