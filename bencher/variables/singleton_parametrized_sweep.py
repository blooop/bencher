"""Singleton variant of ParametrizedSweep (thread-safe).

Provides a per-subclass singleton with the smallest useful surface:

- One instance per subclass via ``__new__``.
- Base ``__init__`` calls the Parametrized chain exactly once.
- ``init_singleton()`` returns a result that is **truthy on first call**
  (backward-compatible with ``if self.init_singleton():``) and also
  works as a **context manager** that auto-resets singleton state when
  the ``with`` block raises during first-time init.
- ``reset_singleton()`` classmethod to manually clear singleton state.
- All operations are **thread-safe** via an internal lock.

Example (boolean style — unchanged from before)::

    class MySweep(ParametrizedSweepSingleton):
        def __init__(self, value=0):
            if self.init_singleton():
                self.value = value  # only set once
            super().__init__()  # safe no-op after the first call

Example (context-manager style — auto-resets on failure)::

    class MySweep(ParametrizedSweepSingleton):
        def __init__(self, **kwargs):
            with self.init_singleton() as is_first:
                if is_first:
                    self._do_fallible_setup(**kwargs)
            super().__init__()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, cast

from .parametrised_sweep import ParametrizedSweep

if TYPE_CHECKING:
    from types import TracebackType


class _SingletonInitResult:
    """Ephemeral result from ``init_singleton()``.

    * **Bool** — ``bool(result)`` is ``True`` when this is the first init.
    * **Context manager** — on ``__exit__``, if the block raised *and* this
      was the first init, singleton bookkeeping is rolled back via
      ``reset_singleton()`` so a subsequent construction can retry.
    """

    __slots__ = ("_cls", "_is_first")

    def __init__(self, cls: type[ParametrizedSweepSingleton], is_first: bool) -> None:
        self._cls = cls
        self._is_first = is_first

    # -- boolean protocol (backward compat) ----------------------------------
    def __bool__(self) -> bool:
        return self._is_first

    # -- context-manager protocol ---------------------------------------------
    def __enter__(self) -> bool:
        return self._is_first

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None and self._is_first:
            self._cls.reset_singleton()
        return False  # never swallow exceptions


class ParametrizedSweepSingleton(ParametrizedSweep):
    """A minimal per-subclass singleton for ParametrizedSweep.

    - Repeated construction returns the same instance for each subclass.
    - Ensures the Parametrized ``__init__`` chain runs only once.
    - ``init_singleton()`` returns a result that is truthy once per subclass
      and doubles as a context manager for automatic rollback on failure.
    - ``reset_singleton()`` explicitly clears singleton state for a subclass.
    - Thread-safe: all shared state is protected by ``_lock``.
    """

    _instances: ClassVar[dict[type, ParametrizedSweepSingleton]] = {}
    _seen: ClassVar[set[type]] = set()
    _lock = threading.Lock()

    def __new__(cls, *_args: Any, **_kwargs: Any) -> Self:
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__new__(cls)
            return cast("Self", cls._instances[cls])

    def __init__(self, **params: Any) -> None:
        # Only run the Parametrized init chain once
        if getattr(self, "_singleton_inited", False):
            return
        super().__init__(**params)
        self._singleton_inited = True

    @classmethod
    def init_singleton(cls) -> _SingletonInitResult:
        """Mark *cls* as seen and return a ``_SingletonInitResult``.

        The result is **truthy** the first time a subclass calls this and
        **falsy** on every subsequent call — identical to the previous boolean
        return value.

        It can also be used as a **context manager**::

            with self.init_singleton() as is_first:
                if is_first:
                    self._fallible_setup()

        If the ``with`` block raises during a first-time init, the singleton
        bookkeeping is rolled back so the next construction can retry cleanly.
        """
        with cls._lock:
            is_first = cls not in cls._seen
            cls._seen.add(cls)
        return _SingletonInitResult(cls, is_first)

    @classmethod
    def reset_singleton(cls) -> None:
        """Clear singleton state for *cls*, allowing re-initialisation."""
        with cls._lock:
            cls._seen.discard(cls)
            cls._instances.pop(cls, None)
