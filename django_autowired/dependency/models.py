from typing import Callable
from typing import List

from pydantic.fields import ModelField


class Dependant(object):
    def __init__(
        self,
        call: Callable,
        ismethod: bool = True,
    ) -> None:
        self.call = call
        self.ismethod = ismethod

        self.path_params: List[ModelField] = []
        self.query_params: List[ModelField] = []
        self.header_params: List[ModelField] = []
        self.cookie_params: List[ModelField] = []
        self.body_params: List[ModelField] = []
        self.dependencies: List[Dependant] = []
