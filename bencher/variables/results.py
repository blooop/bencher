"""Result variable classes for benchmark outputs.

IMPORTANT — hash_persistent() contract:
    Every Result* class MUST implement hash_persistent() using _hash_slots() which hashes
    ALL __slots__ by default. This is critical for the over_time history cache:
    BenchCfg.hash_persistent() includes result variable hashes in the cache key, so a
    non-deterministic hash means historical data can never be found.

    The default behavior hashes every slot. If a slot holds a non-deterministic value
    (runtime objects, callbacks, etc.), add it to _hash_exclude on the class:

        class MyResult(param.Parameter):
            __slots__ = ["units", "obj"]
            _hash_exclude = ("obj",)  # runtime object, not deterministic

            def hash_persistent(self) -> str:
                return _hash_slots(self)

    WRONG — never do this (str(self) includes the memory address for param.Parameter):
        def hash_persistent(self) -> str:
            return hash_sha1(self)

    Tests in test/test_hash_persistent.py auto-discover all Result* classes and verify:
    - Determinism: two equivalent instances produce the same hash
    - Slot coverage: every __slots__ entry is either hashed or in _hash_exclude
    Adding a new class without proper hashing will fail CI.
"""

from __future__ import annotations

import warnings
from enum import auto
from typing import Callable, Any
from functools import partial
import panel as pn
import param
from param import Number
from strenum import StrEnum
import holoviews as hv
from bencher.utils import hash_sha1

# from bencher.variables.parametrised_sweep import ParametrizedSweep


_PARAM_MODULES = frozenset({"param", "param.parameters", "param.parameterized"})


def _hash_slots(instance):
    """Hash all __slots__ from the class hierarchy, excluding non-deterministic attributes.

    Walks the MRO from the concrete class up to (but not including) param framework
    base classes, collecting __slots__ from each ancestor. This supports Result class
    inheritance (e.g. ResultBool extends ResultFloat). Attributes listed in _hash_exclude
    on any class in the hierarchy are skipped.

    The class name is always included in the hash to prevent collisions between different
    Result* classes that share the same slot layout and values (e.g. ResultPath,
    ResultVideo, and ResultImage all have __slots__ = ["units"] with default units="path").
    """
    cls = type(instance)

    # Collect _hash_exclude from the entire hierarchy
    exclude = set()
    for klass in cls.__mro__:
        if getattr(klass, "__module__", "") in _PARAM_MODULES or klass is object:
            break
        exclude.update(getattr(klass, "_hash_exclude", ()))

    # Collect __slots__ from the entire bencher class hierarchy (deduplicating)
    all_slots = []
    seen = set()
    for klass in cls.__mro__:
        if getattr(klass, "__module__", "") in _PARAM_MODULES or klass is object:
            break
        slots = klass.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if slot not in seen and slot not in exclude:
                seen.add(slot)
                all_slots.append(slot)

    values = tuple(getattr(instance, slot) for slot in all_slots)
    return hash_sha1((cls.__name__,) + values)


class OptDir(StrEnum):
    minimize = auto()
    maximize = auto()
    none = auto()  # If none this var will not appear in pareto plots


class ResultFloat(Number):
    """A class to represent continuous float result variables and the desired optimisation direction.

    For boolean (success/failure) outcomes, use ``ResultBool`` instead — it locks
    bounds to [0, 1] and produces correct boolean-style plots.
    """

    __slots__ = ["units", "direction", "share_axis"]
    _hash_exclude = ("share_axis",)  # display-only, not part of benchmark data

    def __init__(self, units="ul", direction: OptDir = OptDir.minimize, share_axis=True, **params):
        Number.__init__(self, **params)
        assert isinstance(units, str)
        self.units = units
        self.default = 0  # json is terrible and does not support nan values
        self.direction = direction
        self.share_axis = share_axis

    def as_dim(self) -> hv.Dimension:
        return hv.Dimension((self.name, self.name), unit=self.units)

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultBool(ResultFloat):
    """A result type for binary outcomes (success/failure, pass/fail, reachable/unreachable).

    Bounds are locked to [0, 1] and plots use boolean-style rendering.
    For continuous scalar metrics (time, distance, score), use ``ResultFloat`` instead.
    """

    def __init__(self, units="ratio", direction: OptDir = OptDir.minimize, default=0, **params):
        super().__init__(units=units, direction=direction, allow_None=True, **params)
        self.default = default
        self.bounds = (0, 1)  # bools are always between 0 and 1


class ResultVec(param.List):
    """A class to represent fixed size vector result variable"""

    __slots__ = ["units", "direction", "size"]

    def __init__(self, size, units="ul", direction: OptDir = OptDir.minimize, **params):
        param.List.__init__(self, **params)
        self.units = units
        self.default = 0  # json is terrible and does not support nan values
        self.direction = direction
        self.size = size

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)

    def index_name(self, idx: int) -> str:
        """given the index of the vector, return the column name that

        Args:
            idx (int): index of the result vector

        Returns:
            str: column name of the vector for the xarray dataset
        """

        mapping = ["x", "y", "z"]
        if idx < 3:
            index = mapping[idx]
        else:
            index = idx
        return f"{self.name}_{index}"

    def index_names(self) -> list[str]:
        """Returns a list of all the xarray column names for the result vector

        Returns:
            list[str]: column names
        """
        return [self.index_name(i) for i in range(self.size)]


class ResultHmap(param.Parameter):
    """A class to represent a holomap return type.

    Note: this class has no __slots__, so _hash_slots hashes only the class name.
    Every ResultHmap instance produces the same hash. This is intentional — there are
    no configuration attributes that would differentiate instances. If a slot is added
    in the future, _hash_slots will automatically include it.
    """

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


def curve(
    x_vals: list[float],
    y_vals: list[float],
    x_name: str,
    y_name: str,
    label: str | None = None,
    **kwargs,
) -> hv.Curve:
    label = label or y_name
    return hv.Curve(zip(x_vals, y_vals), kdims=[x_name], vdims=[y_name], label=label, **kwargs)


class ResultPath(param.Filename):
    __slots__ = ["units"]

    def __init__(self, default=None, units="path", **params):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)

    def to_container(self):
        """Returns a partial function for creating a FileDownload widget with embedding enabled.  This function is used to create a panel container to represent the ResultPath object"""
        return partial(pn.widgets.FileDownload, embed=True)


class ResultVideo(param.Filename):
    __slots__ = ["units"]

    def __init__(self, default=None, units="path", **params):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultImage(param.Filename):
    __slots__ = ["units"]

    def __init__(self, default=None, units="path", **params):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultString(param.String):
    __slots__ = ["units"]

    def __init__(self, default=None, units="str", **params):
        super().__init__(default=default, **params)
        self.units = units

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultContainer(param.Parameter):
    __slots__ = ["units"]

    def __init__(self, default=None, units="container", **params):
        super().__init__(default=default, **params)
        self.units = units

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultReference(param.Parameter):
    """Use this class to save arbitrary objects that are not picklable or native to panel.  You can pass a container callback that takes the object and returns a panel pane to be displayed"""

    __slots__ = ["units", "obj", "container"]
    _hash_exclude = ("obj", "container")  # runtime state, not deterministic config

    def __init__(
        self,
        obj: Any | None = None,
        container: Callable[Any, pn.pane.panel] | None = None,
        default: Any | None = None,
        units: str = "container",
        **params,
    ):
        super().__init__(default=default, **params)
        self.units = units
        self.obj = obj
        self.container = container

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultDataSet(param.Parameter):
    __slots__ = ["units", "obj"]
    _hash_exclude = ("obj",)  # runtime state, not deterministic config

    def __init__(
        self,
        obj: Any | None = None,
        default: Any | None = None,
        units: str = "dataset",
        **params,
    ):
        super().__init__(default=default, **params)
        self.units = units
        self.obj = obj

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultVolume(param.Parameter):
    __slots__ = ["units", "obj"]
    _hash_exclude = ("obj",)  # runtime state, not deterministic config

    def __init__(self, obj=None, default=None, units="container", **params):
        super().__init__(default=default, **params)
        self.units = units
        self.obj = obj

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


PANEL_TYPES = (
    ResultPath,
    ResultImage,
    ResultVideo,
    ResultContainer,
    ResultString,
    ResultReference,
    ResultDataSet,
)


SCALAR_RESULT_TYPES = (ResultFloat, ResultBool)

XARRAY_MULTIDIM_RESULT_TYPES = (
    ResultFloat,
    ResultBool,
    ResultVideo,
    ResultImage,
    ResultString,
    ResultContainer,
    ResultPath,
)

ALL_RESULT_TYPES = (
    ResultFloat,
    ResultBool,
    ResultVec,
    ResultHmap,
    ResultPath,
    ResultVideo,
    ResultImage,
    ResultString,
    ResultContainer,
    ResultDataSet,
    ResultReference,
    ResultVolume,
)


class ResultVar(ResultFloat):
    """Deprecated: use ResultFloat instead."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ResultVar is deprecated, use ResultFloat instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
