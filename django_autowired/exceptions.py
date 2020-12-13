from typing import Optional

from django_autowired import status


class APIException(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "server error"

    def __init__(self, detail: Optional[str] = None) -> None:
        if detail is None:
            detail = self.default_detail

        self.detail = detail


class ValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid input."
