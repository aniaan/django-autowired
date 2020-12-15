import json
from typing import Dict
from typing import Optional
from urllib.parse import urlencode

from django.test import TestCase


class BaseTestCase(TestCase):
    POST = "post"
    PUT = "put"
    GET = "get"
    DELETE = "delete"

    def post_json(self, url, data, query_params: Optional[Dict] = None, **kwargs):
        extra = {}
        if query_params:
            extra["QUERY_STRING"] = urlencode(query_params, doseq=True)
        return self.client.post(
            url, data=json.dumps(data), content_type="application/json", **extra
        )

    def put_json(self, url, data, query_params: Optional[Dict] = None, **kwargs):
        extra = {}
        if query_params:
            extra["QUERY_STRING"] = urlencode(query_params, doseq=True)
        return self.client.put(
            url, data=json.dumps(data), content_type="application/json", **extra
        )

    def delete_json(self, url, data, **kwargs):
        return self.client.delete(
            url, data=json.dumps(data), content_type="application/json"
        )

    def get_json(self, url, data, **kwargs):
        return self.client.get(url, data)

    def method_json_expect_code(
        self,
        method: str,
        code: int,
        url: str,
        data: dict,
        query_params: Optional[Dict] = None,
    ):
        response = getattr(self, method + "_json")(url, data, query_params=query_params)
        self.assertEqual(response.status_code, code)
        content = response.content.decode()
        data = json.loads(content)
        return data
