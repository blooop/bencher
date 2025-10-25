"""Singleton variant of ParametrizedSweep (minimal).

Provides a per-subclass singleton with the smallest useful surface:

- One instance per subclass via ``__new__``.
- Base ``__init__`` calls the Parametrized chain exactly once.
- A simple classmethod ``first_time()`` you can call to know if this
  is the first time the class has been created in this process.

Example
    class MySweep(ParametrizedSweepSingleton):
        def __init__(self, value=0):
            if self.first_time():
                self.value = value  # only set once
            super().__init__()  # safe no-op after the first call
"""

from .parametrised_sweep import ParametrizedSweep


class ParametrizedSweepSingleton(ParametrizedSweep):
    """A minimal per-subclass singleton for ParametrizedSweep.

    - Repeated construction returns the same instance for each subclass.
    - Ensures the Parametrized ``__init__`` chain runs only once.
    - ``first_time()`` returns True once per subclass to gate one-time setup.
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
    def init_singleton(cls) -> bool:
        """Return True the first time a subclass is constructed in this process."""
        if cls in cls._seen:
            return False
        cls._seen.add(cls)
        return True
