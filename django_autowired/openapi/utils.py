from collections import defaultdict
from enum import Enum
from importlib import import_module
from pathlib import PurePath
import re
from types import GeneratorType
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from typing import Type
from typing import Union

from django.conf import settings
from django.http.response import JsonResponse
from django.urls import URLPattern
from django.urls import URLResolver
from django_autowired.logger import logger
from django_autowired.openapi.constants import METHODS_WITH_BODY
from django_autowired.openapi.constants import REF_PREFIX
from django_autowired.openapi.constants import STATUS_CODES_WITH_NO_BODY
from django_autowired.openapi.models import OpenAPI
from django_autowired.params import Body
from django_autowired.params import Param
from django_autowired.route import ViewRoute
from django_autowired.status import HTTP_422_UNPROCESSABLE_ENTITY
from pydantic import BaseModel
from pydantic.fields import ModelField
from pydantic.json import ENCODERS_BY_TYPE
from pydantic.schema import field_schema
from pydantic.schema import get_flat_models_from_fields
from pydantic.schema import get_model_name_map
from pydantic.schema import model_process_schema
from pydantic.utils import lenient_issubclass

validation_error_definition = {
    "title": "ValidationError",
    "type": "object",
    "properties": {
        "loc": {"title": "Location", "type": "array", "items": {"type": "string"}},
        "msg": {"title": "Message", "type": "string"},
        "type": {"title": "Error Type", "type": "string"},
    },
    "required": ["loc", "msg", "type"],
}

validation_error_response_definition = {
    "title": "HTTPValidationError",
    "type": "object",
    "properties": {
        "detail": {
            "title": "Detail",
            "type": "array",
            "items": {"$ref": REF_PREFIX + "ValidationError"},
        }
    },
}

status_code_ranges: Dict[str, str] = {
    "1XX": "Information",
    "2XX": "Success",
    "3XX": "Redirection",
    "4XX": "Client Error",
    "5XX": "Server Error",
    "DEFAULT": "Default Response",
}

SetIntStr = Set[Union[int, str]]
DictIntStrAny = Dict[Union[int, str], Any]


def get_flat_models_from_routes(
    routes: Sequence[Callable],
) -> Set[Union[Type[BaseModel], Type[Enum]]]:
    body_fields_from_routes: List[ModelField] = []
    responses_from_routes: List[ModelField] = []
    request_fields_from_routes: List[ModelField] = []
    for route in routes:
        if getattr(route, "include_in_schema", None) and isinstance(route, ViewRoute):
            if route.body_field:
                assert isinstance(
                    route.body_field, ModelField
                ), "A request body must be a Pydantic Field"
                body_fields_from_routes.append(route.body_field)
            if route.response_field:
                responses_from_routes.append(route.response_field)
            params = route.dependant.get_flat_params()
            request_fields_from_routes.extend(params)

    flat_models = get_flat_models_from_fields(
        body_fields_from_routes + responses_from_routes + request_fields_from_routes,
        known_models=set(),
    )
    return flat_models


def get_model_definitions(
    *,
    flat_models: Set[Union[Type[BaseModel], Type[Enum]]],
    model_name_map: Dict[Union[Type[BaseModel], Type[Enum]], str],
) -> Dict[str, Any]:
    definitions: Dict[str, Dict] = {}
    for model in flat_models:
        # ignore mypy error until enum schemas are released
        m_schema, m_definitions, m_nested_models = model_process_schema(
            model, model_name_map=model_name_map, ref_prefix=REF_PREFIX  # type: ignore
        )
        definitions.update(m_definitions)
        model_name = model_name_map[model]
        definitions[model_name] = m_schema
    return definitions


def generate_operation_id_for_path(*, name: str, path: str, method: str) -> str:
    operation_id = name + path
    operation_id = re.sub("[^0-9a-zA-Z_]", "_", operation_id)
    operation_id = operation_id + "_" + method.lower()
    return operation_id


def generate_operation_id(*, route: ViewRoute, method: str) -> str:
    if route.operation_id:
        return route.operation_id
    path: str = route.path_format
    return generate_operation_id_for_path(name=route.name, path=path, method=method)


def generate_operation_summary(*, route: ViewRoute, method: str) -> str:
    if route.summary:
        return route.summary
    return route.qualname.replace("_", " ").replace(".", " ").title()


def get_openapi_operation_metadata(*, route: ViewRoute, method: str) -> Dict:
    operation: Dict[str, Any] = {}
    if route.tags:
        operation["tags"] = route.tags
    operation["summary"] = generate_operation_summary(route=route, method=method)
    if route.description:
        operation["description"] = route.description
    operation["operationId"] = generate_operation_id(route=route, method=method)
    if route.deprecated:
        operation["deprecated"] = route.deprecated
    return operation


def get_openapi_operation_parameters(
    *,
    all_route_params: Sequence[ModelField],
    model_name_map: Dict[Union[Type[BaseModel], Type[Enum]], str],
) -> List[Dict[str, Any]]:
    parameters = []
    for param in all_route_params:
        field_info = param.field_info
        field_info = cast(Param, field_info)
        # ignore mypy error until enum schemas are released
        parameter = {
            "name": param.alias,
            "in": field_info.in_.value,
            "required": param.required,
            "schema": field_schema(
                param, model_name_map=model_name_map, ref_prefix=REF_PREFIX
            )[
                0
            ],  # type: ignore
        }
        if field_info.description:
            parameter["description"] = field_info.description
        if field_info.deprecated:
            parameter["deprecated"] = field_info.deprecated
        parameters.append(parameter)
    return parameters


def get_openapi_operation_request_body(
    *,
    body_field: Optional[ModelField],
    model_name_map: Dict[Union[Type[BaseModel], Type[Enum]], str],
) -> Optional[Dict]:
    if not body_field:
        return None
    assert isinstance(body_field, ModelField)
    # ignore mypy error until enum schemas are released
    body_schema, _, _ = field_schema(
        body_field, model_name_map=model_name_map, ref_prefix=REF_PREFIX  # type: ignore
    )
    field_info = cast(Body, body_field.field_info)
    request_media_type = field_info.media_type
    required = body_field.required
    request_body_oai: Dict[str, Any] = {}
    if required:
        request_body_oai["required"] = required
    request_body_oai["content"] = {request_media_type: {"schema": body_schema}}
    return request_body_oai


def get_openapi_path(
    *, route: ViewRoute, model_name_map: Dict[Type, str]
) -> Tuple[Dict, Dict]:
    path = {}
    definitions: Dict[str, Any] = {}
    assert route.methods is not None, "Methods must be a list"
    assert route.response_class, "A response class is n" "eeded to generate OpenAPI"
    #
    route_response_media_type = "application/json"
    if route.include_in_schema:
        for method in route.methods:
            operation = get_openapi_operation_metadata(route=route, method=method)
            parameters: List[Dict] = []
            all_route_params = route.dependant.get_flat_params()
            operation_parameters = get_openapi_operation_parameters(
                all_route_params=all_route_params, model_name_map=model_name_map
            )
            parameters.extend(operation_parameters)
            if parameters:
                operation["parameters"] = list(
                    {param["name"]: param for param in parameters}.values()
                )
            if method in METHODS_WITH_BODY:
                request_body_oai = get_openapi_operation_request_body(
                    body_field=route.body_field, model_name_map=model_name_map
                )
                if request_body_oai:
                    operation["requestBody"] = request_body_oai
            status_code = str(route.status_code)
            operation.setdefault("responses", {}).setdefault(status_code, {})[
                "description"
            ] = route.response_description
            if (
                # route_response_media_type
                route.status_code
                not in STATUS_CODES_WITH_NO_BODY
            ):
                response_schema = {"type": "string"}
                if lenient_issubclass(route.response_class, JsonResponse):
                    if route.response_field:
                        response_schema, _, _ = field_schema(
                            route.response_field,
                            model_name_map=model_name_map,
                            ref_prefix=REF_PREFIX,
                        )
                    else:
                        response_schema = {}
                operation.setdefault("responses", {}).setdefault(
                    status_code, {}
                ).setdefault("content", {}).setdefault(route_response_media_type, {})[
                    "schema"
                ] = response_schema
            http422 = str(HTTP_422_UNPROCESSABLE_ENTITY)
            #
            if (all_route_params or route.body_field) and not any(
                [
                    status in operation["responses"]
                    for status in [http422, "4XX", "default"]
                ]
            ):
                operation["responses"][http422] = {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": REF_PREFIX + "HTTPValidationError"}
                        }
                    },
                }
                if "ValidationError" not in definitions:
                    definitions.update(
                        {
                            "ValidationError": validation_error_definition,
                            "HTTPValidationError": validation_error_response_definition,
                        }
                    )
            path[method.lower()] = operation

    return path, definitions


def get_openapi(
    *,
    title: str,
    version: str,
    openapi_version: str = "3.0.2",
    description: Optional[str] = None,
    routes: Sequence,
    tags: Optional[List[Dict[str, Any]]] = None,
) -> Dict:
    info = {"title": title, "version": version}
    if description:
        info["description"] = description
    output: Dict[str, Any] = {"openapi": openapi_version, "info": info}
    components: Dict[str, Dict] = {}
    paths: Dict[str, Dict] = {}
    flat_models = get_flat_models_from_routes(routes)
    # ignore mypy error until enum schemas are released
    model_name_map = get_model_name_map(flat_models)  # type: ignore
    # ignore mypy error until enum schemas are released
    definitions = get_model_definitions(
        flat_models=flat_models, model_name_map=model_name_map  # type: ignore
    )
    # todo: security
    for route in routes:
        if isinstance(route, ViewRoute):
            result = get_openapi_path(route=route, model_name_map=model_name_map)
            if result:
                path, path_definitions = result
                if path:
                    paths.setdefault(route.path_format, {}).update(path)
                if path_definitions:
                    definitions.update(path_definitions)
    if definitions:
        components["schemas"] = {k: definitions[k] for k in sorted(definitions)}
    if components:
        output["components"] = components
    output["paths"] = paths
    if tags:
        output["tags"] = tags
    return jsonable_encoder(OpenAPI(**output), by_alias=True, exclude_none=True)


def generate_encoders_by_class_tuples(
    type_encoder_map: Dict[Any, Callable]
) -> Dict[Callable, Tuple]:
    encoders_by_class_tuples: Dict[Callable, Tuple] = defaultdict(tuple)
    for type_, encoder in type_encoder_map.items():
        encoders_by_class_tuples[encoder] += (type_,)
    return encoders_by_class_tuples


encoders_by_class_tuples = generate_encoders_by_class_tuples(ENCODERS_BY_TYPE)


def jsonable_encoder(
    obj: Any,
    include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
    exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
    by_alias: bool = True,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    custom_encoder: dict = {},
    sqlalchemy_safe: bool = True,
) -> Any:
    if include is not None and not isinstance(include, set):
        include = set(include)
    if exclude is not None and not isinstance(exclude, set):
        exclude = set(exclude)
    if isinstance(obj, BaseModel):
        encoder = getattr(obj.__config__, "json_encoders", {})
        if custom_encoder:
            encoder.update(custom_encoder)
        obj_dict = obj.dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            exclude_defaults=exclude_defaults,
        )
        if "__root__" in obj_dict:
            obj_dict = obj_dict["__root__"]
        return jsonable_encoder(
            obj_dict,
            exclude_none=exclude_none,
            exclude_defaults=exclude_defaults,
            custom_encoder=encoder,
            sqlalchemy_safe=sqlalchemy_safe,
        )
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, (str, int, float, type(None))):
        return obj
    if isinstance(obj, dict):
        encoded_dict = {}
        for key, value in obj.items():
            if (
                (
                    not sqlalchemy_safe
                    or (not isinstance(key, str))
                    or (not key.startswith("_sa"))
                )
                and (value is not None or not exclude_none)
                and ((include and key in include) or not exclude or key not in exclude)
            ):
                encoded_key = jsonable_encoder(
                    key,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                    sqlalchemy_safe=sqlalchemy_safe,
                )
                encoded_value = jsonable_encoder(
                    value,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                    sqlalchemy_safe=sqlalchemy_safe,
                )
                encoded_dict[encoded_key] = encoded_value
        return encoded_dict
    if isinstance(obj, (list, set, frozenset, GeneratorType, tuple)):
        encoded_list = []
        for item in obj:
            encoded_list.append(
                jsonable_encoder(
                    item,
                    include=include,
                    exclude=exclude,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                    sqlalchemy_safe=sqlalchemy_safe,
                )
            )
        return encoded_list

    if custom_encoder:
        if type(obj) in custom_encoder:
            return custom_encoder[type(obj)](obj)
        else:
            for encoder_type, encoder in custom_encoder.items():
                if isinstance(obj, encoder_type):
                    return encoder(obj)

    if type(obj) in ENCODERS_BY_TYPE:
        return ENCODERS_BY_TYPE[type(obj)](obj)
    for encoder, classes_tuple in encoders_by_class_tuples.items():
        if isinstance(obj, classes_tuple):
            return encoder(obj)

    errors: List[Exception] = []
    try:
        data = dict(obj)
    except Exception as e:
        errors.append(e)
        try:
            data = vars(obj)
        except Exception as e:
            errors.append(e)
            raise ValueError(errors)
    return jsonable_encoder(
        data,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
        custom_encoder=custom_encoder,
        sqlalchemy_safe=sqlalchemy_safe,
    )


class OpenAPISchemaGenerator(object):
    def __init__(
        self,
        *,
        title: str = "",
        version: str = "",
        openapi_version: str = "3.0.2",
        description: Optional[str] = None,
        urlpatterns: Optional[List[URLPattern]] = None,
        view_route: Dict[Callable, ViewRoute],
    ):
        self.title = title
        self.version = version
        self.openapi_version = openapi_version
        self.description = description
        self.patterns = urlpatterns
        self.view_route = view_route

        if urlpatterns is None:
            # Use the default Django URL conf
            urlconf = settings.ROOT_URLCONF

            # Load the given URLconf module
            if isinstance(urlconf, str):
                urls = import_module(urlconf)
            else:
                urls = urlconf
            if hasattr(urls, "urlpatterns"):
                self.patterns = urls.urlpatterns  # type: ignore
        self.set_route_path()

    def set_route_path(self):
        # get all path
        endpoints = self.get_api_endpoints()
        routes = self.view_route
        self.routes = []
        for r in routes.keys():
            fun_name = ".".join(r.__qualname__.split(".")[:-1])
            for e in endpoints:
                path, callback = e
                if callback.__qualname__ == fun_name:
                    routes[r].set_path(path)
                    self.routes.append(routes[r])
                    continue

    def get_api_endpoints(
        self,
        patterns: Optional[List[URLPattern]] = None,
        prefix: str = "",
        app_name: Optional[str] = None,
        namespace: Optional[str] = None,
        ignored_endpoints: Optional[Set] = None,
    ) -> List[Tuple[str, Any]]:
        if patterns is None:
            patterns = self.patterns

        api_endpoints = []
        if ignored_endpoints is None:
            ignored_endpoints = set()

        if patterns:
            for pattern in patterns:
                path_regex = prefix + str(pattern.pattern)
                if isinstance(pattern, URLPattern):
                    try:
                        path = self.get_path_from_regex(path_regex)
                        callback = pattern.callback
                        if path in ignored_endpoints:
                            continue
                        ignored_endpoints.add(path)

                        endpoint = (path, callback)
                        api_endpoints.append(endpoint)
                    except Exception:
                        logger.warning("failed to enumerate view", exc_info=True)

                elif isinstance(pattern, URLResolver):
                    nested_endpoints = self.get_api_endpoints(
                        patterns=pattern.url_patterns,
                        prefix=path_regex,
                        app_name="%s:%s" % (app_name, pattern.app_name)
                        if app_name
                        else pattern.app_name,
                        namespace="%s:%s" % (namespace, pattern.namespace)
                        if namespace
                        else pattern.namespace,
                        ignored_endpoints=ignored_endpoints,
                    )
                    api_endpoints.extend(nested_endpoints)
                else:
                    raise TypeError(f"unknown pattern type {type(pattern)}")

        return api_endpoints

    @staticmethod
    def replace_named_groups(pattern: str) -> str:
        r"""
        Find named groups in `pattern` and replace them with the group name. E.g.,
        1. ^(?P<a>\w+)/b/(\w+)$ ==> ^<a>/b/(\w+)$
        2. ^(?P<a>\w+)/b/(?P<c>\w+)/$ ==> ^<a>/b/<c>/$
        """
        named_group_matcher = re.compile(r"\(\?P(<\w+>)")
        named_group_indices = [
            (m.start(0), m.end(0), m.group(1))
            for m in named_group_matcher.finditer(pattern)
        ]
        # Tuples of (named capture group pattern, group name).
        group_pattern_and_name = []
        # Loop over the groups and their start and end indices.
        for start, end, group_name in named_group_indices:
            # Handle nested parentheses, e.g. '^(?P<a>(x|y))/b'.
            unmatched_open_brackets, prev_char = 1, None
            for idx, val in enumerate(list(pattern[end:])):
                # If brackets are balanced, the end of the string for the current
                # named capture group pattern has been reached.
                if unmatched_open_brackets == 0:
                    group_pattern_and_name.append(
                        (pattern[start : end + idx], group_name)
                    )
                    break

                # Check for unescaped `(` and `)`. They mark the start and end of a
                # nested group.
                if val == "(" and prev_char != "\\":
                    unmatched_open_brackets += 1
                elif val == ")" and prev_char != "\\":
                    unmatched_open_brackets -= 1
                prev_char = val

        # Replace the string for named capture groups with their group names.
        for group_pattern, group_name in group_pattern_and_name:
            pattern = pattern.replace(group_pattern, group_name)
        return pattern

    @staticmethod
    def replace_unnamed_groups(pattern: str) -> str:
        r"""
        Find unnamed groups in `pattern` and replace them with '<var>'. E.g.,
        1. ^(?P<a>\w+)/b/(\w+)$ ==> ^(?P<a>\w+)/b/<var>$
        2. ^(?P<a>\w+)/b/((x|y)\w+)$ ==> ^(?P<a>\w+)/b/<var>$
        """
        unnamed_group_matcher = re.compile(r"\(")
        unnamed_group_indices = [
            m.start(0) for m in unnamed_group_matcher.finditer(pattern)
        ]
        # Indices of the start of unnamed capture groups.
        group_indices = []
        # Loop over the start indices of the groups.
        for start in unnamed_group_indices:
            # Handle nested parentheses, e.g. '^b/((x|y)\w+)$'.
            unmatched_open_brackets, prev_char = 1, None
            for idx, val in enumerate(list(pattern[start + 1 :])):
                if unmatched_open_brackets == 0:
                    group_indices.append((start, start + 1 + idx))
                    break

                # Check for unescaped `(` and `)`. They mark the start and end of
                # a nested group.
                if val == "(" and prev_char != "\\":
                    unmatched_open_brackets += 1
                elif val == ")" and prev_char != "\\":
                    unmatched_open_brackets -= 1
                prev_char = val

        # Remove unnamed group matches inside other unnamed capture groups.
        group_start_end_indices = []
        prev_end = None
        for start, end in group_indices:
            if prev_end and start > prev_end or not prev_end:
                group_start_end_indices.append((start, end))
            prev_end = end

        if group_start_end_indices:
            # Replace unnamed groups with <var>. Handle the fact that replacing the
            # string between indices will change string length and thus indices
            # will point to the wrong substring if not corrected.
            final_pattern, prev_end = [], None
            for start, end in group_start_end_indices:
                if prev_end:
                    final_pattern.append(pattern[prev_end:start])
                final_pattern.append(pattern[:start] + "<var>")
                prev_end = end
            final_pattern.append(pattern[prev_end:])
            return "".join(final_pattern)
        else:
            return pattern

    @classmethod
    def simplify_regex(cls, pattern: str) -> str:
        r"""
        Clean up urlpattern regexes into something more readable by humans. For
        example, turn "^(?P<sport_slug>\w+)/athletes/(?P<athlete_slug>\w+)/$"
        into "/<sport_slug>/athletes/<athlete_slug>/".
        """
        pattern = cls.replace_named_groups(pattern)
        pattern = cls.replace_unnamed_groups(pattern)
        # clean up any outstanding regex-y characters.
        pattern = pattern.replace("^", "").replace("$", "").replace("?", "")
        if not pattern.startswith("/"):
            pattern = "/" + pattern
        return pattern

    @classmethod
    def unescape(cls, s) -> str:
        """Unescape all backslash escapes from `s`.
        :param str s: string with backslash escapes
        :rtype: str
        """
        # unlike .replace('\\', ''), this corectly transforms a double backslash
        # into a single backslash
        return re.sub(r"\\(.)", r"\1", s)

    @classmethod
    def unescape_path(cls, path: str) -> str:
        """Remove backslashe escapes from all path components outside {parameters}.
        This is needed becausen ``simplify_regex`` does not handle this correctly.

        **NOTE:** this might destructively affect some url regex patterns
        that contain metacharacters (e.g. \\w, \\d)
        outside path parameter groups; if you are in this category, God help you

        :param str path: path possibly containing
        :return: the unescaped path
        :rtype: str
        """
        PATH_PARAMETER_RE = re.compile(r"{(?P<parameter>\w+)}")
        clean_path = ""
        while path:
            match = PATH_PARAMETER_RE.search(path)
            if not match:
                clean_path += cls.unescape(path)
                break
            clean_path += cls.unescape(path[: match.start()])
            clean_path += match.group()
            path = path[match.end() :]
        return clean_path

    @classmethod
    def get_path_from_regex(cls, path_regex: str):
        if path_regex.endswith(")"):
            logger.warning(
                "url pattern does not end in $ ('%s') - unexpected things might happen",
                path_regex,
            )
        path = cls.simplify_regex(path_regex)
        _PATH_PARAMETER_COMPONENT_RE = re.compile(
            r"<(?:(?P<converter>[^>:]+):)?(?P<parameter>\w+)>"
        )
        # Strip Django 2.0 convertors as they are incompatible with uritemplate format
        res = re.sub(_PATH_PARAMETER_COMPONENT_RE, r"{\g<parameter>}", path)
        return cls.unescape_path(res)

    def get_schema(self) -> Dict:
        return get_openapi(
            title=self.title,
            version=self.version,
            openapi_version=self.openapi_version,
            description=self.description,
            routes=self.routes,
        )
