from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from pydantic import BaseModel
from tests.base import BaseTestCase


class Item(BaseModel):
    name: str
    tags: List[str] = []
    tag_set: Set[str] = set()


class ListFieldView(View):
    @autowired(description="this is list-field view")
    def put(self, request: HttpRequest, item: Item):
        return JsonResponse(data={"tags": item.tags, "tag_set": list(item.tag_set)})


class Image(BaseModel):
    url: str
    name: str


class NestedItem(BaseModel):
    name: str
    image: Optional[Image] = None


class ListItem(BaseModel):
    images: Optional[List[Image]] = None


class Offer(BaseModel):
    items: List[ListItem]


class NestedFieldView(View):
    @autowired(description="this is nested-field view")
    def put(self, request: HttpRequest, item: NestedItem):
        return JsonResponse(data=item.dict())


class DeeplyFieldView(View):
    @autowired(description="this is deeply-field view")
    def put(self, request: HttpRequest, offer: Offer):
        return JsonResponse(data=offer.dict())


class BodyPureListView(View):
    @autowired(description="this is pure-list view")
    def put(self, request: HttpRequest, images: List[Image]):
        return JsonResponse(data=[image.dict() for image in images], safe=False)


class BodyDictView(View):
    @autowired(description="this is body-list view")
    def put(self, request: HttpRequest, data: Dict[str, float]):
        return JsonResponse(data=data)


urlpatterns = [
    path(route="list-field/", view=ListFieldView.as_view()),
    path(route="nested-field/", view=NestedFieldView.as_view()),
    path(route="deeply-field/", view=DeeplyFieldView.as_view()),
    path(route="pure-list/", view=BodyPureListView.as_view()),
    path(route="body-dict/", view=BodyDictView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_body_nested")
class TestListFieldView(BaseTestCase):
    def test_validate_error(self):
        case = {"name": "one", "tags": [{}], "tag_set": ["1"]}
        self.method_json_expect_code(
            method=self.PUT,
            code=400,
            url="/list-field/",
            data=case,
        )

    def test_success(self):
        case = {"name": "one", "tags": ["1", "2"], "tag_set": ["1", "1"]}
        data = self.method_json_expect_code(
            method=self.PUT,
            code=200,
            url="/list-field/",
            data=case,
        )

        self.assertEqual(data["tags"], case["tags"])
        assert 1 == len(data["tag_set"])


@override_settings(ROOT_URLCONF="tests.test_body_nested")
class TestNestedFieldView(BaseTestCase):
    def test_success(self):
        case = {"name": "one", "image": {"url": "www.google.com", "name": "google"}}
        data = self.method_json_expect_code(
            method=self.PUT,
            code=200,
            url="/nested-field/",
            data=case,
        )

        self.assertDictEqual(case, data)


@override_settings(ROOT_URLCONF="tests.test_body_nested")
class TestDeeplyFieldView(BaseTestCase):
    def test_success(self):
        case = {
            "items": [
                {
                    "images": [
                        {"url": "http://example.com/baz.jpg", "name": "The Foo live"},
                        {"url": "http://example.com/dave.jpg", "name": "The Baz"},
                    ]
                },
                {
                    "images": [
                        {"url": "http://example.com/baz.jpg", "name": "The Foo live"},
                        {"url": "http://example.com/dave.jpg", "name": "The Baz"},
                    ]
                },
            ]
        }
        data = self.method_json_expect_code(
            method=self.PUT,
            code=200,
            url="/deeply-field/",
            data=case,
        )

        self.assertEqual(case, data)


@override_settings(ROOT_URLCONF="tests.test_body_nested")
class TestBodyPureListView(BaseTestCase):
    def test_success(self):
        case = [
            {"url": "http://example.com/baz.jpg", "name": "The Foo live"},
            {"url": "http://example.com/dave.jpg", "name": "The Baz"},
        ]
        data = self.method_json_expect_code(
            method=self.PUT,
            code=200,
            url="/pure-list/",
            data=case,
        )

        self.assertEqual(case, data)


@override_settings(ROOT_URLCONF="tests.test_body_nested")
class TestBodyDictView(BaseTestCase):
    def test_success(self):
        # case = {1:[1, 2, 3]}
        case = {"1": 1.0}
        data = self.method_json_expect_code(
            method=self.PUT,
            code=200,
            url="/body-dict/",
            data=case,
        )

        self.assertEqual(case, data)

    def test_error(self):
        case = {1: [1, 2, 3]}
        self.method_json_expect_code(
            method=self.PUT,
            code=400,
            url="/body-dict/",
            data=case,
        )
