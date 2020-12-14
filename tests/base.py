import json

from django.test import TestCase


class BaseTestCase(TestCase):
    POST = "post"
    PUT = "put"
    GET = "get"
    DELETE = "delete"

    def post_json(self, url, data):
        return self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

    def put_json(self, url, data):
        return self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )

    def delete_json(self, url, data):
        return self.client.delete(
            url, data=json.dumps(data), content_type="application/json"
        )

    def get_json(self, url, data):
        return self.client.get(url, data)

    def method_json_expect_code(self, method: str, code: int, url: str, data: dict):
        response = getattr(self, method + "_json")(url, data)
        self.assertEqual(response.status_code, code)
        content = response.content.decode()
        data = json.loads(content)
        return data
