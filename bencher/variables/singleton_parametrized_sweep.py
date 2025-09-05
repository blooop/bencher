from .parametrised_sweep import ParametrizedSweep


class SingletonParametrizedSweep(ParametrizedSweep):
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
        super().__init__(**params)
        self._singleton_initialized = True

    @classmethod
    def reset_singletons(cls) -> None:
        """Clear the singleton instance cache for all subclasses.

        Intended primarily for tests to ensure isolation between test cases without
        reaching into protected attributes from outside the class.
        """
        cls._instances.clear()
