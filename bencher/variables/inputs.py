from enum import Enum
from typing import List, Any, Dict

import numpy as np
from param import Integer, Number, Selector
from bencher.variables.sweep_base import SweepBase, shared_slots


class SweepSelector(Selector, SweepBase):
    """A class representing a parameter sweep for selectable options.

    This class extends both Selector and SweepBase to provide parameter sweeping
    capabilities for categorical variables that have a predefined set of options.

    Attributes:
        units (str): The units of measurement for the parameter
        samples (int): The number of samples to take from the available options
    """

    __slots__ = shared_slots

    def __init__(self, units: str = "ul", samples: int = None, **params):
        SweepBase.__init__(self)
        Selector.__init__(self, **params)

        self.units = units
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples

    def values(self) -> List[Any]:
        """Return all the values for the parameter sweep.

        Returns:
            List[Any]: A list of parameter values to sweep through
        """
        return self.indices_to_samples(self.samples, self.objects)


class BoolSweep(SweepSelector):
    """A class representing a parameter sweep for boolean values.

    This class extends SweepSelector to provide parameter sweeping capabilities
    specifically for boolean values (True and False).

    Attributes:
        units (str): The units of measurement for the parameter
        samples (int): The number of samples to take (typically 2 for booleans)
    """

    def __init__(self, units: str = "ul", samples: int = None, default: bool = True, **params):
        SweepSelector.__init__(
            self,
            units=units,
            samples=samples,
            default=default,
            objects=[True, False] if default else [False, True],
            **params,
        )


class StringSweep(SweepSelector):
    """A class representing a parameter sweep for string values.

    This class extends SweepSelector to provide parameter sweeping capabilities
    specifically for a list of string values.

    Attributes:
        units (str): The units of measurement for the parameter
        samples (int): The number of samples to take from the available strings
    """

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
    """A class representing a parameter sweep for enum values.

    This class extends SweepSelector to provide parameter sweeping capabilities
    specifically for enumeration types, supporting both enum types and lists of enum values.

    Attributes:
        units (str): The units of measurement for the parameter
        samples (int): The number of samples to take from the available enum values
    """

    __slots__ = shared_slots

    def __init__(
        self, enum_type: Enum | List[Enum], units: str = "ul", samples: int = None, **params
    ):
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
    """A class representing a parameter sweep for integer values.

    This class extends both Integer and SweepBase to provide parameter sweeping capabilities
    specifically for integer values within specified bounds or with custom sample values.

    Attributes:
        units (str): The units of measurement for the parameter
        samples (int): The number of samples to take from the range
        sample_values (List[int], optional): Specific integer values to use as samples instead of
            generating them from bounds. If provided, overrides the samples parameter.
    """

    __slots__ = shared_slots + ["sample_values"]

    def __init__(
        self, units: str = "ul", samples: int = None, sample_values: List[int] = None, **params
    ):
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

    def values(self) -> List[int]:
        """Return all the values for the parameter sweep.

        If sample_values is provided, returns those values. Otherwise generates values
        within the specified bounds.

        Returns:
            List[int]: A list of integer values to sweep through
        """
        sample_values = (
            self.sample_values
            if self.sample_values is not None
            else list(range(int(self.bounds[0]), int(self.bounds[1] + 1)))
        )

        return self.indices_to_samples(self.samples, sample_values)

    ###THESE ARE COPIES OF INTEGER VALIDATION BUT ALSO ALLOW NUMPY INT TYPES
    def _validate_value(self, val, allow_None):
        if callable(val):
            return

        if allow_None and val is None:
            return

        if not isinstance(val, (int, np.integer)):
            raise ValueError(
                "Integer parameter %r must be an integer, not type %r." % (self.name, type(val))
            )

    ###THESE ARE COPIES OF INTEGER VALIDATION BUT ALSO ALLOW NUMPY INT TYPES
    def _validate_step(self, val, step):
        if step is not None and not isinstance(step, (int, np.integer)):
            raise ValueError("Step can only be None or an integer value, not type %r" % type(step))


class FloatSweep(Number, SweepBase):
    """A class representing a parameter sweep for floating point values.

    This class extends both Number and SweepBase to provide parameter sweeping capabilities
    specifically for floating point values within specified bounds or with custom sample values.

    Attributes:
        units (str): The units of measurement for the parameter
        samples (int): The number of samples to take from the range
        sample_values (List[float], optional): Specific float values to use as samples instead of
            generating them from bounds. If provided, overrides the samples parameter.
        step (float, optional): Step size between samples when generating values from bounds
    """

    __slots__ = shared_slots + ["sample_values"]

    def __init__(
        self,
        units: str = "ul",
        samples: int = 10,
        sample_values: List[float] = None,
        step: float = None,
        **params,
    ):
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

    def values(self) -> List[float]:
        """Return all the values for the parameter sweep.

        If sample_values is provided, returns those values. Otherwise generates values
        within the specified bounds, either using linspace (when step is None) or arange.

        Returns:
            List[float]: A list of float values to sweep through
        """
        samps = self.samples
        if self.sample_values is None:
            if self.step is None:
                return np.linspace(self.bounds[0], self.bounds[1], samps)

            return np.arange(self.bounds[0], self.bounds[1], self.step)
        return self.sample_values


def box(name: str, center: float, width: float) -> FloatSweep:
    """Create a FloatSweep parameter centered around a value with a given width.

    This is a convenience function to create a bounded FloatSweep parameter with
    bounds centered on a specific value, extending by the width in both directions.

    Args:
        name (str): The name of the parameter
        center (float): The center value of the parameter
        width (float): The distance from the center to the bounds in both directions

    Returns:
        FloatSweep: A FloatSweep parameter with the specified name, default, and bounds
    """
    var = FloatSweep(default=center, bounds=(center - width, center + width))
    var.name = name
    return var


def p(
    name: str, values: List[Any] = None, samples: int = None, max_level: int = None
) -> Dict[str, Any]:
    """
    Create a parameter dictionary with optional values, samples, and max_level.

    Args:
        name (str): The name of the parameter.
        values (List[Any], optional): A list of values for the parameter. Defaults to None.
        samples (int, optional): The number of samples. Must be greater than 0 if provided. Defaults to None.
        max_level (int, optional): The maximum level. Must be greater than 0 if provided. Defaults to None.

    Returns:
        Dict[str, Any]: A dictionary containing the parameter details.
    """
    if max_level is not None and max_level <= 0:
        raise ValueError("max_level must be greater than 0")

    if samples is not None and samples <= 0:
        raise ValueError("samples must be greater than 0")
    return {"name": name, "values": values, "max_level": max_level, "samples": samples}


def with_level(arr: list, level: int) -> list:
    """Apply level-based sampling to a list of values.

    This function uses an IntSweep with the provided values and applies level-based
    sampling to it, returning the resulting values.

    Args:
        arr (list): List of values to sample from
        level (int): The sampling level to apply (higher levels provide more samples)

    Returns:
        list: The level-sampled values
    """
    return IntSweep(sample_values=arr).with_level(level).values()
    # return tmp.with_sample_values(arr).with_level(level).values()
