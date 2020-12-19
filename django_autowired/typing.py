from typing import Any
from typing import Callable
from typing import Iterable
from typing import Type
from typing import Union

from django.core.files.uploadedfile import UploadedFile as DjangoUploadFile
from django.utils.datastructures import MultiValueDict

ViewFunc = Callable

# Waiting for mypy to support recursion
JSON = Any
BodyType = Union[JSON, MultiValueDict]


class UploadFile(DjangoUploadFile):
    @classmethod
    def __get_validators__(cls: Type["UploadFile"]) -> Iterable[Callable]:
        yield cls.validate

    @classmethod
    def validate(cls: Type["UploadFile"], v: Any) -> Any:
        if not isinstance(v, DjangoUploadFile):
            raise ValueError(f"Expected UploadFile, received: {type(v)}")
        return v
