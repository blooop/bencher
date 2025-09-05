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
