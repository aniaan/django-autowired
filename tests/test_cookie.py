from http.cookies import SimpleCookie
from typing import Optional

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.params import Cookie
from tests.base import BaseTestCase


class CookieView(View):
    @autowired(description="this is cookie-field view")
    def get(self, request: HttpRequest, ads_id: Optional[str] = Cookie(None)):
        return JsonResponse(data={"ads_id": ads_id})


urlpatterns = [
    path(route="cookie/", view=CookieView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_cookie")
class TestListFieldView(BaseTestCase):
    def test_success(self):
        self.client.cookies = SimpleCookie({"ads_id": "abc"})
        data = self.method_json_expect_code(
            method=self.GET,
            code=200,
            url="/cookie/",
            data={},
        )

        assert data["ads_id"] == "abc"

    def test_success1(self):
        data = self.method_json_expect_code(
            method=self.GET,
            code=200,
            url="/cookie/",
            data={},
        )

        assert data["ads_id"] is None

    def test_success2(self):
        self.client.cookies = SimpleCookie({"ads_id": 123})
        data = self.method_json_expect_code(
            method=self.GET,
            code=200,
            url="/cookie/",
            data={},
        )

        assert data["ads_id"] == "123"
