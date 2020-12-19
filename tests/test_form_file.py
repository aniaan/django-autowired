import io

from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from django_autowired.autowired import autowired
from django_autowired.param_func import File
from django_autowired.param_func import Form
from django_autowired.typing import UploadFile
from tests.base import BaseTestCase


class FormFileView(View):
    @autowired(description="this is form-view")
    def post(
        self,
        request: HttpRequest,
        file: UploadFile = File(...),
        username: str = Form(...),
        password: str = Form(...),
    ):
        return JsonResponse(
            data={"size": file.size, "username": username, "password": password}
        )


urlpatterns = [
    path(route="form-file-view/", view=FormFileView.as_view()),
]


@override_settings(ROOT_URLCONF="tests.test_form_file")
class TestFormView(BaseTestCase):
    def test_success(self):
        bs = io.BytesIO(b"file view")
        case = {"username": "demo", "password": "dp", "file": bs}
        data = self.method_json_expect_code(
            method=self.POST,
            code=200,
            url="/form-file-view/",
            data=case,
            content_type=None,
        )
        self.assertEqual(
            data, {"username": "demo", "password": "dp", "size": bs.getbuffer().nbytes}
        )
