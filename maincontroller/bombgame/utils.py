from abc import ABC, abstractmethod
from asyncio import get_running_loop, iscoroutinefunction, Lock as AsyncLock, run_coroutine_threadsafe, CancelledError
from asyncio.locks import Event
from collections import deque
from concurrent.futures import Executor, Future
from logging import getLogger
from signal import signal, SIGINT
from threading import Thread, RLock, Condition
from typing import Any, Union, Callable, NamedTuple, Awaitable, Dict, TypeVar, Deque, Tuple, Sequence, Mapping

K = TypeVar("K")
V = TypeVar("V")


class EventSource:
    """A mixin class that provides event listener functionality."""

    def __init__(self):
        self.__listeners = []
        self.__loop = get_running_loop()

    def add_listener(self, eventclass: type, callback: Callable[[Any], Any], reentrant: bool = False) -> None:
        lock = None if reentrant else AsyncLock()
        self.__listeners.append((eventclass, callback, lock))

    def remove_listener(self, eventclass: type, callback: Callable[[Any], Any]) -> None:
        try:
            for listener in self.__listeners:
                if listener[0] == eventclass and listener[1] == callback:
                    self.__listeners.remove(listener)
        except ValueError:
            raise ValueError("listener not found") from None

    def trigger(self, event: Any) -> None:
        getLogger("EventSource").debug("%s raised on %s", event, self)
        for (eventclass, callback, lock) in self.__listeners:
            if isinstance(event, eventclass):
                run_coroutine_threadsafe(log_errors(_call_event(callback, lock, event)), self.__loop)


async def _call_event(callback, lock, event):
    if lock is not None:
        await lock.acquire()
    try:
        if iscoroutinefunction(callback):
            await callback(event)
        else:
            callback(event)
    finally:
        if lock is not None:
            lock.release()


class Registry(Dict[K, V]):
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
    _queue: Deque[Tuple[Callable, Sequence, Mapping, Future]]

    def __init__(self, *, name, **kwargs):
        super().__init__(name=name, daemon=True, **kwargs)
        self.logger = getLogger(self.name)
        self._lock = RLock()
        self._cond = Condition(self._lock)
        self._queue = deque()
        self._quit = False

    def run(self):
        try:
            self._run()
        except SystemExit:
            pass
        except BaseException as ex:  # pylint: disable=broad-except
            self.logger.error("Uncaught %s in %s: %s", ex.__class__.__name__, self.name, ex, exc_info=True)

    def _get_task(self, timeout=None, process_all=False):
        with self._lock:
            self._cond.wait_for(lambda: self._queue or self._quit, timeout)
            done = (not self._queue) if process_all else self._quit
            return None if done else self._queue.popleft()

    def enqueue(self, task):
        with self._lock:
            if not self._quit:
                self._queue.append(task)
                self._cond.notify_all()

    def stop(self):
        with self._lock:
            self._quit = True
            self._cond.notify_all()

    @abstractmethod
    def _run(self):
        pass


class AuxiliaryThreadExecutor(Executor, AuxiliaryThread):
    def submit(self, func, *args, **kwargs):
        future = Future()
        self.enqueue((func, args, kwargs, future))
        return future

    def __enter__(self):
        self.start()
        return self

    def shutdown(self, wait=True):
        if self.is_alive():
            self.stop()
            if wait:
                self.join()

    def _run(self):
        while self._queue or not self._quit:
            task = self._get_task(process_all=True)
            if task is None:
                continue
            func, args, kwargs, future = task
            self._run_task(func, args, kwargs, future)

    @staticmethod
    def _run_task(func, args, kwargs, future):
        if not future.set_running_or_notify_cancel():
            return
        try:
            result = func(*args, **kwargs)
        except BaseException as ex:  # pylint: disable=broad-except
            future.set_exception(ex)
        else:
            future.set_result(result)


class FatalError(Exception):
    """A fatal error in a bomb subsystem that causes the game to become unplayable."""


class VersionNumber(NamedTuple):
    """A major/minor version number."""
    major: int
    minor: int

    def __str__(self):
        return f"{self.major}.{self.minor}"


async def log_errors(awaitable: Awaitable):
    try:
        return await awaitable
    except CancelledError:
        raise
    except BaseException as ex:
        get_running_loop().call_exception_handler({
            "exception": ex
        })
        raise


def handle_sigint():
    quit_evt = Event()
    get_running_loop().add_signal_handler(SIGINT, lambda: quit_evt.set())
    return quit_evt
