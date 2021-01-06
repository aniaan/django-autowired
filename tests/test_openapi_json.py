from typing import Dict
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.openapi.utils import OpenAPISchemaGenerator
from django_autowired.param_func import Body
from pydantic import BaseModel
from tests.base import BaseTestCase


class Items(BaseModel):
    items: Dict[str, int]


class FooView(View):
    @autowired(response_model=Items)
    def post(
            self,
            request: HttpRequest,
            items: Items = Body(..., embed=True),
    ):
        return JsonResponse(items)


autowired.setup_schema()
urlpatterns = [
    path(route="openapi.json", view=autowired.get_openapi_view()),
    path(route="swagger", view=autowired.get_swagger_ui_view()),
    path(route="items/", view=FooView.as_view()),
]

openapi_schema = {
    "components": {
        "schemas": {
            "HTTPValidationError": {
                "properties": {
                    "detail": {
                        "title": "Detail",
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ValidationError"},
                    }
                },
                "title": "HTTPValidationError",
                "type": "object",
            },
            "ValidationError": {
                "properties": {
                    "loc": {
                        "items": {"type": "string"},
                        "title": "Location",
                        "type": "array",
                    },
                    "msg": {"title": "Message", "type": "string"},
                    "type": {"title": "Error Type", "type": "string"},
                },
                "required": ["loc", "msg", "type"],
                "title": "ValidationError",
                "type": "object",
            },
            "pydantic__main__Items": {
                "properties": {
                    "items": {
                        "additionalProperties": {"type": "integer"},
                        "title": "Items",
                        "type": "object",
                    }
                },
                "required": ["items"],
                "title": "Items",
                "type": "object",
            },
            "tests__test_openapi_json__Items": {
                "properties": {
                    "items": {
                        "additionalProperties": {"type": "integer"},
                        "title": "Items",
                        "type": "object",
                    }
                },
                "required": ["items"],
                "title": "Items",
                "type": "object",
            },
        }
    },
    "openapi": "3.0.2",
    "info": {"title": "test", "version": "0.1.0"},
    "paths": {
        "/items/": {
            "post": {
                "operationId": "post_items__post",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/tests__test_openapi_json__Items"}
                        }
                    },
                    "required": True,
                },
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    '$ref': '#/components/schemas/pydantic__main__Items'
                                }
                            }
                        },
                        "description": "Successful Response",
                    },
                    "422": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/HTTPValidationError"
                                }
                            }
                        },
                        "description": "Validation Error",
                    },
                },
                "summary": "Fooview Post",
            },
        }
    },
}


@override_settings(ROOT_URLCONF="tests.test_body")
class TestOpenapiSchema(BaseTestCase):
    # def test_open_api(self):
    #     response = self.get_json(url='/openapi.json', data=None)
    #     print(response.json())

    def test_get_json(self):
        generator = OpenAPISchemaGenerator(
            title="test",
            version="0.1.0",
            urlpatterns=urlpatterns,
            view_route=autowired.view_route
        )
        res = generator.get_schema()
        assert res == openapi_schema

# @override_settings(ROOT_URLCONF="tests.test_body")
# class TestSwaggerSchema(BaseTestCase):
#     def test_swagger(self):
#         response = self.client.get('/swagger')
#         print(response.content)
