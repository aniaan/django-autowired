from typing import Any, Callable
from typing import Union
from typing import Mapping
from typing import List

from django.utils.datastructures import MultiValueDict

ViewFunc = Callable

# Waiting for mypy to support recursion
JSON = Any
BodyType = Union[JSON, MultiValueDict]
