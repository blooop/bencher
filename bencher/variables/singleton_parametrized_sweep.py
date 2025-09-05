from .parametrised_sweep import ParametrizedSweep


class ParametrizedSweepSingleton(ParametrizedSweep):
    """Base class that adds singleton behavior to ParametrizedSweep."""

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

        Intended primarily for tests to ensure isolation between test cases without
        reaching into protected attributes from outside the class.
        """
        cls._instances.clear()

    def init_singleton(self, initializer=None, **params) -> bool:
        """Run subclass initialization exactly once and finalize the singleton.

        This helper removes boilerplate from subclasses. Use it inside your
        subclass __init__ like:

            def __init__(self, some_arg=1):
            if self.init_singleton():
                self.field = some_arg

        Args:
            initializer (Callable[[], None] | None): Optional function that sets up instance fields.
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
