from enum import Enum
from typing import List, Any

import numpy as np
from param import Integer, Number, Selector
from bencher.variables.sweep_base import SweepBase, shared_slots


class SweepSelector(Selector, SweepBase):
    """A class to reprsent a parameter sweep of bools"""

    __slots__ = shared_slots

    def __init__(self, units: str = "ul", samples: int = None, **params):
        SweepBase.__init__(self)
        Selector.__init__(self, **params)

        self.units = units
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples

    def values(self, level: int) -> List[Any]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        return self.level_to_samples(level, self.objects)


class BoolSweep(SweepSelector):
    """A class to reprsent a parameter sweep of bools"""

    def __init__(self, units: str = "ul", samples: int = None, default=True, **params):
        SweepSelector.__init__(
            self,
            units=units,
            samples=samples,
            default=default,
            objects=[True, False] if default else [False, True],
            **params,
        )


class StringSweep(SweepSelector):
    """A class to reprsent a parameter sweep of strings"""

    def __init__(
        self,
        string_list: List[str],
        units: str = "ul",
        samples: int = None,
        **params,
    ):
        SweepSelector.__init__(
            self,
            objects=string_list,
            instantiate=True,
            units=units,
            samples=samples,
            **params,
        )


class EnumSweep(SweepSelector):
    """A class to reprsent a parameter sweep of enums"""

    __slots__ = shared_slots

    def __init__(self, enum_type: Enum | List[Enum], units="ul", samples=None, **params):
        # The enum can either be an Enum type or a list of enums
        list_of_enums = isinstance(enum_type, list)
        selector_list = enum_type if list_of_enums else list(enum_type)
        SweepSelector.__init__(
            self,
            objects=selector_list,
            instantiate=True,
            units=units,
            samples=samples,
            **params,
        )
        if not list_of_enums:  # Grab the docs from the enum type def
            self.doc = enum_type.__doc__


class IntSweep(Integer, SweepBase):
    """A class to reprsent a parameter sweep of ints"""

    __slots__ = shared_slots + ["sample_values"]

    def __init__(self, units="ul", samples=None, sample_values=None, **params):
        SweepBase.__init__(self)
        Integer.__init__(self, **params)

        self.units = units

        if sample_values is None:
            if samples is None:
                if self.bounds is None:
                    raise RuntimeError("You must define bounds for integer types")
                self.samples = 1 + self.bounds[1] - self.bounds[0]
            else:
                self.samples = samples
            self.sample_values = None
        else:
            self.sample_values = sample_values
            self.samples = len(self.sample_values)
            if "default" not in params:
                self.default = sample_values[0]

    def values(self, level: int) -> List[int]:
        """return all the values for a parameter sweep.  If debug is true return the  list"""
        sample_values = (
            self.sample_values
            if self.sample_values is not None
            else list(range(int(self.bounds[0]), int(self.bounds[1] + 1)))
        )

        return self.level_to_samples(level, sample_values)

    ###THESE ARE COPIES OF INTEGER VALIDATION BUT ALSO ALLOW NUMPY INT TYPES
    def _validate_value(self, val, allow_None):
        if callable(val):
            return

        if allow_None and val is None:
            return

        if not isinstance(val, (int, np.integer)):
            raise ValueError(
                "Integer parameter %r must be an integer, " "not type %r." % (self.name, type(val))
            )

    ###THESE ARE COPIES OF INTEGER VALIDATION BUT ALSO ALLOW NUMPY INT TYPES
    def _validate_step(self, val, step):
        if step is not None and not isinstance(step, (int, np.integer)):
            raise ValueError(
                "Step can only be None or an " "integer value, not type %r" % type(step)
            )


class FloatSweep(Number, SweepBase):
    """A class to represent a parameter sweep of floats"""

    __slots__ = shared_slots + ["sample_values"]

    def __init__(self, units="ul", samples=10, sample_values=None, step=None, **params):
        SweepBase.__init__(self)
        Number.__init__(self, step=step, **params)

        self.units = units
        self.sample_values = sample_values

        if sample_values is None:
            self.samples = samples
        else:
            self.samples = len(self.sample_values)
            if "default" not in params:
                self.default = sample_values[0]

    def values(self, level: int) -> List[float]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        if self.sample_values is None:
            if self.step is None:
                if level == 0:
                    samps = self.samples
                else:
                    samps = self.define_level(level)
                return np.linspace(self.bounds[0], self.bounds[1], samps)
            sample_values= np.arange(self.bounds[0], self.bounds[1], self.step)
        else:
            sample_values= self.sample_values

        return self.level_to_samples(level, sample_values)
