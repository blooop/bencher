from enum import Enum
from typing import List

import numpy as np
from param import Boolean, Integer, Number, Selector
from bencher.variables.sweep_base import SweepBase, shared_slots

# pylint: disable=super-init-not-called


class BoolSweep(SweepBase, Boolean):
    """A class to reprsent a parameter sweep of bools"""

    __slots__ = shared_slots

    def __init__(self, units: str = "ul", samples: int = None, samples_debug: int = 2, **params):
        Boolean.__init__(self, **params)
        self.units = units
        if samples is None:
            self.samples = 2
        self.samples_debug = samples_debug

    def values(self, debug=False) -> List[bool]:  # pylint disable=unused-argument
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        return [True, False]


class StringSweep(SweepBase, Selector):
    """A class to reprsent a parameter sweep of strings"""

    __slots__ = shared_slots

    def __init__(
        self,
        string_list: List[str],
        units: str = "ul",
        samples: int = None,
        samples_debug: int = 2,
        **params,
    ):
        Selector.__init__(self, string_list, instantiate=True, **params)
        self.units = units
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples
        self.samples_debug = min(self.samples, samples_debug)

    def values(self, debug=False) -> List[str]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        return self.objects


class EnumSweep(SweepBase, Selector):
    """A class to reprsent a parameter sweep of enums"""

    __slots__ = shared_slots

    def __init__(
        self, enum_type: Enum | List[Enum], units="ul", samples=None, samples_debug=2, **params
    ):
        # The enum can either be an Enum type or a list of enums
        list_of_enums = type(enum_type) is list
        if list_of_enums:
            selector_list = enum_type  # already a list of enums
        else:
            # create a list of enums from the enum type definition
            selector_list = list(enum_type)
        Selector.__init__(self, selector_list, **params)
        if not list_of_enums:  # Grab the docs from the enum type def
            self.doc = enum_type.__doc__
        self.units = units
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples
        self.samples_debug = min(self.samples, samples_debug)

    def values(self, debug=False) -> List[Enum]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        if debug:
            outputs = [self.objects[0], self.objects[-1]]
        else:
            outputs = self.objects
        return outputs


class IntSweep(SweepBase, Integer):
    """A class to reprsent a parameter sweep of ints"""

    __slots__ = shared_slots + ["sample_values"]

    def __init__(self, units="ul", samples=None, samples_debug=2, sample_values=None, **params):
        Integer.__init__(self, **params)
        self.units = units
        self.samples_debug = samples_debug

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

    def values(self, debug=False) -> List[int]:
        """return all the values for a parameter sweep.  If debug is true return the  list"""
        samps = self.samples_debug if debug else self.samples

        if self.sample_values is None:
            return [
                int(i)
                for i in np.linspace(
                    self.bounds[0], self.bounds[1], samps, endpoint=True, dtype=int
                )
            ]
        if debug:
            indices = [
                int(i)
                for i in np.linspace(0, len(self.sample_values) - 1, self.samples_debug, dtype=int)
            ]
            return [self.sample_values[i] for i in indices]
        return self.sample_values

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


class FloatSweep(SweepBase, Number):
    """A class to represent a parameter sweep of floats"""

    __slots__ = shared_slots + ["sample_values"]

    def __init__(self, units="ul", samples=10, samples_debug=2, sample_values=None, **params):
        Number.__init__(self, **params)
        self.units = units
        self.samples_debug = samples_debug
        if sample_values is None:
            self.samples = samples
            self.sample_values = None
        else:
            self.sample_values = sample_values
            self.samples = len(self.sample_values)
            if "default" not in params:
                self.default = sample_values[0]

    def values(self, debug=False) -> List[float]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        samps = self.samples_debug if debug else self.samples
        if self.sample_values is None:
            return np.linspace(self.bounds[0], self.bounds[1], samps)
        if debug:
            indices = [
                int(i)
                for i in np.linspace(0, len(self.sample_values) - 1, self.samples_debug, dtype=int)
            ]
            return [self.sample_values[i] for i in indices]
        return self.sample_values