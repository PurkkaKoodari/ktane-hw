from typing import Any, Union, Callable

class EventSource:
    """A mixin class that provides event listener functionality."""

    def __init__(self):
        self.__listeners = []

    def add_listener(self, eventclass: type, callback: Callable) -> None:
        self.__listeners.append((eventclass, callback))

    def remove_listener(self, eventclass: type, callback: Callable) -> None:
        try:
            self.__listeners.remove((eventclass, callback))
        except ValueError:
            raise ValueError("listener not found") from None

    def trigger(self, event: Any) -> None:
        for (eventclass, callback) in self.__listeners:
            if isinstance(event, eventclass):
                callback(self, event)

class Registry(dict):
    """A registry for registering classes.

    Nothing more but a glorified dict that provides the register() method.
    """

    __slots__ = ("_field",)

    def __init__(self, field: Union[None, str] = None):
        super().__init__()
        if field is not None:
            self._field = field

    def register(self, id_or_class):
        """
        A decorator that adds the decorated class to the registry with all the ids provided as argument.
        """
        if self._field is not None:
            if not isinstance(id_or_class, type):
                raise ValueError("don't give an argument to Registry.register when using an identifier field")
            self._register(id_or_class, getattr(id_or_class, self._field))
            return id_or_class
        else:
            def register(class_):
                self._register(class_, id_or_class)
                return class_
            return register

    def _register(self, class_, id_):
        if id_ in self:
            raise ValueError(f"id {id_} already present in registry")
        self[id_] = class_

class UngettableMeta(type):
    def __get__(cls, _1, _2):
        raise NotImplementedError

class Ungettable(metaclass=UngettableMeta):
    pass
