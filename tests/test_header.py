from typing import Optional

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.params import Header
from tests.base import BaseTestCase


class HeaderView(View):
    @autowired(description="this is header-field view")
    def get(
        self,
        request: HttpRequest,
        x_token: Optional[str] = Header(None),
        X_TOKEN: Optional[str] = Header(None),
    ):
        return JsonResponse(data={"x_token": x_token, "X_TOKEN": X_TOKEN})


urlpatterns = [
    path(route="header/", view=HeaderView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_header")
class TestHeaderView(BaseTestCase):
    def test_success(self):
        header = {"HTTP_X_TOKEN": "header"}
        data = self.method_json_expect_code(
            method=self.GET, code=200, url="/header/", data={}, **header
        )

        assert data["x_token"] == "header"
        assert data["X_TOKEN"] == "header"
