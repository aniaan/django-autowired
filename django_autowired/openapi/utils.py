import http.client
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Type, Union, cast

# from fastapi import routing
# from fastapi.datastructures import DefaultPlaceholder
# from fastapi.dependencies.models import Dependant
# from fastapi.dependencies.utils import get_flat_dependant, get_flat_params
# from fastapi.encoders import jsonable_encoder
# from fastapi.openapi.constants import (
#     METHODS_WITH_BODY,
#     REF_PREFIX,
#     STATUS_CODES_WITH_NO_BODY,
# )
# from fastapi.openapi.models import OpenAPI
# from fastapi.params import Body, Param
# from fastapi.utils import (
#     deep_dict_update,
#     generate_operation_id_for_path,
#     get_model_definitions,
# )
# from pydantic import BaseModel
from pydantic.fields import ModelField
from pydantic.schema import (
    field_schema,
    get_flat_models_from_fields,
    get_model_name_map,
)
from pydantic.utils import lenient_issubclass
# from starlette.responses import JSONResponse
# from starlette.routing import BaseRoute
# from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

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
            # "items": {"$ref": REF_PREFIX + "ValidationError"},
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



def get_openapi(
    *,
    title: str,
    version: str,
    openapi_version: str = "3.0.2",
    description: Optional[str] = None,
    routes: Sequence,
    tags: Optional[List[Dict[str, Any]]] = None,
    servers: Optional[List[Dict[str, Union[str, Any]]]] = None,
) -> Dict:
    info = {"title": title, "version": version}
    if description:
        info["description"] = description
    output: Dict[str, Any] = {"openapi": openapi_version, "info": info}
    if servers:
        output["servers"] = servers
    components: Dict[str, Dict] = {}
    paths: Dict[str, Dict] = {}
    # flat_models = get_flat_models_from_routes(routes)
    # # ignore mypy error until enum schemas are released
    # model_name_map = get_model_name_map(flat_models)  # type: ignore
    # # ignore mypy error until enum schemas are released
    # definitions = get_model_definitions(
    #     flat_models=flat_models, model_name_map=model_name_map  # type: ignore
    # )
    # for route in routes:
    #     if isinstance(route, routing.APIRoute):
    #         result = get_openapi_path(route=route, model_name_map=model_name_map)
    #         if result:
    #             path, security_schemes, path_definitions = result
    #             if path:
    #                 paths.setdefault(route.path_format, {}).update(path)
    #             if security_schemes:
    #                 components.setdefault("securitySchemes", {}).update(
    #                     security_schemes
    #                 )
    #             if path_definitions:
    #                 definitions.update(path_definitions)
    # if definitions:
    #     components["schemas"] = {k: definitions[k] for k in sorted(definitions)}
    # if components:
    #     output["components"] = components
    # output["paths"] = paths
    # if tags:
    #     output["tags"] = tags
    # return jsonable_encoder(OpenAPI(**output), by_alias=True, exclude_none=True)
    return {"test": "123"}
