from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.param_func import Path
from tests.base import BaseTestCase


class ClassPathView(View):
    @autowired(description="this is class-path view")
    def get(
        self,
        request: HttpRequest,
        id: int = Path(gt=20),
        name: str = Path(min_length=2, max_length=3),
    ):
        return JsonResponse(data={"id": id, "name": name})


@autowired(description="this is func-path view")
def func_path_view(
    request: HttpRequest,
    id: int = Path(gt=30, le=40),
    name: str = Path(min_length=2, max_length=3),
):
    return JsonResponse(data={"id": id, "name": name})


urlpatterns = [
    path(route="class-path/<int:id>/<str:name>", view=ClassPathView.as_view()),
    path(route="func-path/<int:id>/<str:name>", view=func_path_view),
]


@override_settings(ROOT_URLCONF="tests.test_path")
class TestClassPathView(BaseTestCase):
    def test_success(self):
        data = self.method_json_expect_code(
            method=self.GET, code=200, url="/class-path/21/bea", data={}
        )
        assert data["id"] == 21
        assert data["name"] == "bea"

    def test_validate_error(self):
        self.method_json_expect_code(
            method=self.GET, code=400, url="/class-path/10/bea", data={}
        )
        self.method_json_expect_code(
            method=self.GET, code=400, url="/class-path/21/bean", data={}
        )


@override_settings(ROOT_URLCONF="tests.test_path")
class TestFuncPathView(BaseTestCase):
    def test_success(self):
        data = self.method_json_expect_code(
            method=self.GET, code=200, url="/func-path/40/bea", data={}
        )
        assert data["id"] == 40
        assert data["name"] == "bea"

    def test_validate_error(self):
        self.method_json_expect_code(
            method=self.GET, code=400, url="/func-path/10/bea", data={}
        )
        self.method_json_expect_code(
            method=self.GET, code=400, url="/func-path/33/bean", data={}
        )
