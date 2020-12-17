from typing import Optional

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.param_func import Body
from pydantic import BaseModel
from pydantic.fields import Field
from tests.base import BaseTestCase


class Item(BaseModel):
    name: str
    description: Optional[str] = Field(
        None, title="The description of the item", max_length=3
    )
    price: float = Field(
        ...,
        gt=0,
        description="The price must be greater than zero",
    )
    tax: Optional[float] = None


class BodyFieldView(View):
    @autowired(description="this is body-field view")
    def put(self, request: HttpRequest, item: Item = Body(..., embed=True)):
        return JsonResponse(data=item.dict())


urlpatterns = [
    path(route="body-field/", view=BodyFieldView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_body_field")
class TestBodyFieldView(BaseTestCase):
    def test_validate_error(self):
        case = {"item": {"name": "one", "description": "abcd", "price": -1}}
        self.method_json_expect_code(
            method=self.PUT,
            code=400,
            url="/body-field/",
            data=case,
        )

    def test_validate_error1(self):
        case = {"item": {"name": "one", "description": "abc", "price": -1}}
        self.method_json_expect_code(
            method=self.PUT,
            code=400,
            url="/body-field/",
            data=case,
        )

    def test_success(self):
        case = {"item": {"name": "one", "description": "abc", "price": 1}}
        data = self.method_json_expect_code(
            method=self.PUT,
            code=200,
            url="/body-field/",
            data=case,
        )
        case["item"]["tax"] = None

        self.assertDictEqual(data, case["item"])
