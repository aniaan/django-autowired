from typing import List
from typing import Optional

from django.http.request import HttpRequest
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from pydantic import BaseModel
from tests.base import BaseTestCase


class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None
    tags: List[str] = []


class CreateView(View):
    @autowired(description="this is create-view", response_model=Item)
    def post(self, request: HttpRequest, item: Item):
        return item


class UserIn(BaseModel):
    username: str
    password: str
    email: str
    full_name: Optional[str] = None


class UserOut(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None


class OutputView(View):
    @autowired("this is output-view", response_model=UserOut)
    def post(self, request: HttpRequest, user: UserIn):
        return user


urlpatterns = [
    path(route="create/", view=CreateView.as_view()),
    path(route="output/", view=OutputView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_response_model")
class TestCreateView(BaseTestCase):
    def test_success1(self):
        case = {"name": "item_name", "price": 2.3}
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/create/",
            data=case,
        )

        self.assertDictEqual(
            data, {**case, "description": None, "tax": None, "tags": []}
        )


@override_settings(ROOT_URLCONF="tests.test_response_model")
class TestOutputView(BaseTestCase):
    def test_success1(self):
        case = {
            "username": "item_name",
            "password": "2.3",
            "email": "a@gmail.com",
            "full_name": "full",
        }
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/output/",
            data=case,
        )

        self.assertDictEqual(
            data,
            {
                "username": "item_name",
                "email": "a@gmail.com",
                "full_name": "full",
            },
        )
