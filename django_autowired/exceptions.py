import http
from typing import Any
from typing import Sequence

from pydantic import create_model
from pydantic import ValidationError
from pydantic.error_wrappers import ErrorList

RequestErrorModel = create_model("Request")


class APIException(Exception):
    def __init__(self, status_code: int, detail: str = None) -> None:
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase
        self.status_code = status_code
        self.detail = detail


class RequestValidationError(ValidationError):
    def __init__(self, errors: Sequence[ErrorList], *, body: Any = None) -> None:
        self.body = body
        super().__init__(errors, RequestErrorModel)
