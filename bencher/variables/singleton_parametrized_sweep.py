"""Singleton variant of ParametrizedSweep.

This module provides a base class for creating Param "param.Parameterized"-based
benchmark sweep classes that are instantiated exactly once per subclass. The
singleton semantics help when:

- You wire a sweep class into BenchRunner or other orchestration that may
  construct the class multiple times during a session.
- You want per-class state to persist across reruns (e.g., caches, buffers,
  heavy initializations) without redoing work.
- You need deterministic, single-time initialization while still using the
  familiar ParametrizedSweep interface.

Key features
- One instance per subclass: repeated construction returns the same object.
- First-time initialization helpers:
  - override "on_first_init()" to run setup once with zero boilerplate; or
  - use "init_singleton()" in your __init__ to guard setup explicitly.
- Test support: call "reset_singletons()" between tests to avoid leaks.

Usage examples
1) Hook-based (no guards):
    class MySweep(SingletonParametrizedSweep):
        theta = FloatSweep(default=0, bounds=[0, 1])

        def on_first_init(self):
            self.cache = {}

2) Guard-based (explicit, pylint-friendly):
    class MySweep(SingletonParametrizedSweep):
        def __init__(self):
            if self.init_singleton():
                self.cache = {}
            super().__init__()  # safe no-op after the first call
"""

from .parametrised_sweep import ParametrizedSweep


class ParametrizedSweepSingleton(ParametrizedSweep):
    """A ParametrizedSweep that guarantees a single instance per subclass.

    This class implements a per-subclass singleton using __new__. Subclasses can
    initialize their one-time state in either of two ways:

    - Override on_first_init(): Called exactly once prior to the Parametrized
      init chain; ideal when you prefer no guards in your __init__.
    - Call init_singleton() from __init__: Returns True on the first call, so
      you can conditionally set fields and then call super().__init__().

    See reset_singletons() for a testing aid that clears the singleton cache.
    """

    _instances = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
            cls._instances[cls]._singleton_initialized = False
        return cls._instances[cls]

    def __init__(self, **params):
        # Only initialize once due to singleton pattern, including all subclass logic
        if getattr(self, "_singleton_initialized", False):
            return
        # Hook for subclasses that prefer a no-boilerplate override point
        try:
            self.on_first_init()  # type: ignore[attr-defined]
        except AttributeError:
            # Subclass did not define the hook; that's fine
            pass
        super().__init__(**params)
        self._singleton_initialized = True

    # Optional template hook for subclasses that want zero guard boilerplate
    # Subclasses may override this and set up fields. It is called exactly once.
    def on_first_init(self) -> None:  # pragma: no cover - optional hook
        pass

    @classmethod
    def reset_singletons(cls) -> None:
        """Clear the singleton instance cache for all subclasses.

        Intended primarily for tests to ensure isolation between test cases
        without reaching into protected attributes from outside the class.
        """
        cls._instances.clear()

    def init_singleton(self, initializer=None, **params) -> bool:
        """Run subclass initialization exactly once and finalize the singleton.

        Use inside your subclass __init__ to avoid manual guards. If you pass an
        initializer, it is invoked only on the first call, before the parent
        ParametrizedSweep initialization.

        Example:
            if self.init_singleton():
                self.buf = []
            super().__init__()

        Args:
            initializer (Callable[[], None] | None): Optional one-time setup function.
            **params: Optional params forwarded to ParametrizedSweep.__init__.

        Returns:
            bool: True if initialization ran this call, False if already initialized.
        """
        if getattr(self, "_singleton_initialized", False):
            return False
        if initializer is not None:
            initializer()
        # Call the Parametrized init chain once
        super().__init__(**params)
        self._singleton_initialized = True
        return True
