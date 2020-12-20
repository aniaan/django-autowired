import json
from typing import Any
from typing import Dict
from typing import Optional
from urllib.parse import urlencode

from django.test import TestCase


class BaseTestCase(TestCase):
    POST = "post"
    PUT = "put"
    GET = "get"
    DELETE = "delete"

    def post_json(
        self,
        url,
        data,
        query_params: Optional[Dict] = None,
        content_type: Optional[str] = "application/json",
        **kwargs
    ):
        extra = {}
        if query_params:
            extra["QUERY_STRING"] = urlencode(query_params, doseq=True)

        if content_type == "application/json":
            data = json.dumps(data)
            extra["content_type"] = content_type

        return self.client.post(url, data=data, **extra, **kwargs)

    def put_json(self, url, data, query_params: Optional[Dict] = None, **kwargs):
        extra = {}
        if query_params:
            extra["QUERY_STRING"] = urlencode(query_params, doseq=True)
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type="application/json",
            **extra,
            **kwargs
        )

    def delete_json(self, url, data, **kwargs):
        return self.client.delete(
            url, data=json.dumps(data), content_type="application/json", **kwargs
        )

    def get_json(self, url, data, **kwargs):
        return self.client.get(url, data, **kwargs)

    def method_json_expect_code(
        self,
        method: str,
        code: int,
        url: str,
        data: Any,
        query_params: Optional[Dict] = None,
        **kwargs
    ):
        response = getattr(self, method + "_json")(
            url, data, query_params=query_params, **kwargs
        )
        self.assertEqual(response.status_code, code)
        content = response.content.decode()
        data = json.loads(content)
        return data
