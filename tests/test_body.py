from copy import copy
from typing import Optional

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.openapi.utils import OpenAPISchemaGenerator
from django_autowired.param_func import Body
from django_autowired.param_func import Path
from django_autowired.param_func import Query
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from tests.base import BaseTestCase


class Item(BaseModel):
    id: int
    name: str
    price: float
    desc: str = FieldInfo(default="", requierd=False)
    city: Optional[str] = None


class ClassBodyView(View):
    @autowired(description="this is class-body view")
    def post(
            self,
            request: HttpRequest,
            name: str,
            item: Item,
            id: int = Path(..., gt=20),
            limit: Optional[int] = 100,
            page: Optional[int] = Query(default=11, ge=10, le=20),
    ):
        return JsonResponse(
            data={
                "id": id,
                "name": name,
                "limit": limit,
                "page": page,
                "item": {
                    "id": item.id,
                    "name": item.name,
                    "price": item.price,
                    "desc": item.desc,
                    "city": item.city,
                },
            }
        )


class EmbedBodyView(View):
    @autowired(description="this is embed-body view")
    def post(self, request: HttpRequest, item: Item = Body(..., embed=True)):
        return JsonResponse(data=item.dict())


class MultiFieldBodyView(View):
    @autowired(description="this is a multi-field-body view")
    def post(self, item: Item, item1: Item, user_id: int = Body(...)):
        return JsonResponse(
            data={"item": item.dict(), "item1": item1.dict(), "user_id": user_id}
        )


autowired.setup_schema()
urlpatterns = [
    path(route="openapi.json", view=autowired.get_openapi_view()),
    path(route="swagger", view=autowired.get_swagger_ui_view()),
    path(route="class-body/<int:id>/", view=ClassBodyView.as_view()),
    path(route="embed-body/", view=EmbedBodyView.as_view()),
    path(route="multi-field-body/", view=MultiFieldBodyView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_body")
class TestOpenapiSchema(BaseTestCase):
    # def test_open_api(self):
    #     response = self.get_json(url='/openapi.json', data=None)
    #     print(response.json())

    def test_get_json(self):
        generator = OpenAPISchemaGenerator(urlpatterns=urlpatterns, view_route=autowired._view_route)
        res = generator.get_schema()
        print(res)


@override_settings(ROOT_URLCONF="tests.test_body")
class TestSwaggerSchema(BaseTestCase):
    def test_swagger(self):
        response = self.client.get('/swagger')
        print(response.content)


@override_settings(ROOT_URLCONF="tests.test_body")
class TestClassBodyView(BaseTestCase):
    def test_missing_body(self):
        case = {"id": 111, "name": "item_name", "price": 2.3}
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/class-body/21/",
            data=case,
            query_params={"name": "bea", "limit": "14", "page": "13"},
        )

        assert data["id"] == 21
        assert data["name"] == "bea"
        assert data["limit"] == 14
        assert data["page"] == 13

        result = copy(case)
        result["city"] = None
        result["desc"] = ""
        self.assertDictEqual(data["item"], result)

    def test_full_body(self):
        case = {
            "id": 111,
            "name": "item_name",
            "price": 2.3,
            "desc": "this good",
            "city": "bei",
        }
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/class-body/21/",
            data=case,
            query_params={"name": "bea", "limit": "14", "page": "13"},
        )

        assert data["id"] == 21
        assert data["name"] == "bea"
        assert data["limit"] == 14
        assert data["page"] == 13

        self.assertDictEqual(data["item"], case)

    def test_validate_error(self):
        case = {
            "id": "fwf",
            "name": "item_name",
            "price": 2.3,
            "desc": "this good",
            "city": "bei",
        }
        self.method_json_expect_code(
            method=self.POST,
            code=400,
            url="/class-body/21/",
            data=case,
            query_params={"name": "bea", "limit": "14", "page": "13"},
        )

    def test_validate_error1(self):
        case = {
            "item": {
                "id": "fwf",
                "name": "item_name",
                "price": 2.3,
                "desc": "this good",
                "city": "bei",
            }
        }
        self.method_json_expect_code(
            method=self.POST,
            code=400,
            url="/class-body/21/",
            data=case,
            query_params={"name": "bea", "limit": "14", "page": "13"},
        )


@override_settings(ROOT_URLCONF="tests.test_body")
class TestEmbedBodyView(BaseTestCase):
    def test_error(self):
        case = {
            "id": 111,
            "name": "item_name",
            "price": 2.3,
            "desc": "this good",
            "city": "bei",
        }
        self.method_json_expect_code(
            method=self.POST,
            code=400,
            url="/embed-body/",
            data=case,
        )

    def test_success(self):
        case = {
            "item": {
                "id": 111,
                "name": "item_name",
                "price": 2.3,
                "desc": "this good",
                "city": "bei",
            }
        }
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/embed-body/",
            data=case,
        )

        self.assertEqual(data, case["item"])


@override_settings(ROOT_URLCONF="tests.test_body")
class TestMultiFieldBody(BaseTestCase):
    def test_success(self):
        case = {
            "item": {
                "id": 111,
                "name": "item_name",
                "price": 2.3,
                "desc": "this good",
                "city": "bei",
            },
            "item1": {
                "id": 111,
                "name": "item_name",
                "price": 2.3,
                "desc": "this good",
                "city": "bei",
            },
            "user_id": 12,
        }

        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/multi-field-body/",
            data=case,
        )

        self.assertEqual(data, case)
