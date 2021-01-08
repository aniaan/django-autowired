import json
import os
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
            view_route=autowired.view_route,
        )
        res = generator.get_schema()
        file_path = os.path.join(os.getcwd(), "tests/openapi_json/sample.json")
        with open(file_path, "r") as f:
            openapi_schema = json.load(f)
        assert res == openapi_schema


# @override_settings(ROOT_URLCONF="tests.test_body")
# class TestSwaggerSchema(BaseTestCase):
#     def test_swagger(self):
#         response = self.client.get('/swagger')
#         print(response.content)
