"""Singleton variant of ParametrizedSweep (minimal).

Provides a per-subclass singleton with the smallest useful surface:

- One instance per subclass via ``__new__``.
- Base ``__init__`` calls the Parametrized chain exactly once.
- ``init_singleton()`` returns a result that is **truthy on first call**
  (backward-compatible with ``if self.init_singleton():``) and also
  works as a **context manager** that auto-resets singleton state when
  the ``with`` block raises during first-time init.
- ``reset_singleton()`` classmethod to manually clear singleton state.

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

from .parametrised_sweep import ParametrizedSweep


class _SingletonInitResult:
    """Ephemeral result from ``init_singleton()``.

    * **Bool** — ``bool(result)`` is ``True`` when this is the first init.
    * **Context manager** — on ``__exit__``, if the block raised *and* this
      was the first init, singleton bookkeeping (``_seen`` / ``_instances``)
      is rolled back so a subsequent construction can retry.
    """

    __slots__ = ("_cls", "_is_first")

    def __init__(self, cls, is_first: bool):
        self._cls = cls
        self._is_first = is_first

    # -- boolean protocol (backward compat) ----------------------------------
    def __bool__(self) -> bool:
        return self._is_first

    # -- context-manager protocol ---------------------------------------------
    def __enter__(self):
        return self._is_first

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self._is_first:
            self._cls._seen.discard(self._cls)
            self._cls._instances.pop(self._cls, None)
        return False  # never swallow exceptions


class ParametrizedSweepSingleton(ParametrizedSweep):
    """A minimal per-subclass singleton for ParametrizedSweep.

    - Repeated construction returns the same instance for each subclass.
    - Ensures the Parametrized ``__init__`` chain runs only once.
    - ``init_singleton()`` returns a result that is truthy once per subclass
      and doubles as a context manager for automatic rollback on failure.
    - ``reset_singleton()`` explicitly clears singleton state for a subclass.
    """

    _instances = {}
    _seen = set()

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, **params):
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
        is_first = cls not in cls._seen
        cls._seen.add(cls)
        return _SingletonInitResult(cls, is_first)

    @classmethod
    def reset_singleton(cls) -> None:
        """Clear singleton state for *cls*, allowing re-initialisation."""
        cls._seen.discard(cls)
        cls._instances.pop(cls, None)
