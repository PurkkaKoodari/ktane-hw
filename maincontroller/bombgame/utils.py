from abc import ABC, abstractmethod
from collections import deque
from logging import getLogger
from typing import Any, Union, Callable
from threading import Thread, Lock, Condition

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

class AuxiliaryThread(Thread, ABC):
    def __init__(self, *args, name, **kwargs):
        super().__init__(*args, name=name, **kwargs)
        self.logger = getLogger(self.name)
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._queue = deque()
        self._quit = False

    def run(self):
        try:
            self._run()
        except SystemExit:
            pass
        except BaseException as ex:
            self.logger.error("Uncaught %s in %s: %s", ex.__class__.__name__, self.name, ex, exc_info=True)

    def _get_task(self, timeout=None):
        with self._lock:
            self._cond.wait_for(lambda: self._queue or self._quit, timeout)
            return None if self._quit else self._queue.popleft()

    def enqueue(self, task):
        with self._lock:
            self._queue.append(task)
            self._cond.notify_all()

    def stop(self):
        with self._lock:
            self._quit = True
            self._cond.notify_all()

    @abstractmethod
    def _run(self):
        pass
