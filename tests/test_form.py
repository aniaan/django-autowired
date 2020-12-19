from typing import List

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.param_func import Form
from tests.base import BaseTestCase


class FormView(View):
    @autowired(description="this is form-view")
    def post(
        self, request: HttpRequest, username: str = Form(...), password: str = Form(...)
    ):
        return JsonResponse(data={"username": username, "password": password})


class MultiValueFormView(View):
    @autowired(description="this is multivalue-form-view")
    def post(
        self,
        request: HttpRequest,
        tags: List[str] = Form(...),
        ages: List[int] = Form(...),
    ):
        return JsonResponse(data={"tags": tags, "ages": ages})


urlpatterns = [
    path(route="form-view/", view=FormView.as_view()),
    path(route="multi-value-view/", view=MultiValueFormView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_form")
class TestFormView(BaseTestCase):
    def test_success(self):
        case = {"username": "demo", "password": "dp"}
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/form-view/",
            data=case,
            content_type=None,
        )
        self.assertEqual(data, case)


@override_settings(ROOT_URLCONF="tests.test_form")
class TestMultiValueFormView(BaseTestCase):
    def test_success(self):
        case = {"tags": ["a", "b"], "ages": [1, 2, 3]}
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/multi-value-view/",
            data=case,
            content_type=None,
        )
        self.assertEqual(data, case)
