from collections.abc import Callable
from typing import Any


class Signal:
    def __init__(self):
        self._listeners: list[Callable[..., None]] = []

    def connect(self, listener: Callable[..., None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def disconnect(self, listener: Callable[..., None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def send(self, *args: Any, **kwargs: Any) -> None:
        for listener in list(self._listeners):
            listener(*args, **kwargs)
