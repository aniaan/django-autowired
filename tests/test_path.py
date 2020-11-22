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
    def get(self, request: HttpRequest, id: int = Path(default=None, gt=20)):
        return JsonResponse(data={"id": id})


@autowired(description="this is func-path view")
def func_path_view(request: HttpRequest, id: int = Path(default=None, gt=20)):
    return JsonResponse(data={"id": id})


urlpatterns = [
    path(route="class-path/<int:id>/", view=ClassPathView.as_view()),
    path(route="func-path/<int:id>/", view=func_path_view),
]


@override_settings(ROOT_URLCONF="tests.test_path")
class TestClassPathView(BaseTestCase):
    def test_success(self):
        data = self.method_json_expect_code(
            method=self.GET, code=200, url="/class-path/10/", data={}
        )
        assert data["id"], 11
