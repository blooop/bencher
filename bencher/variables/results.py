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

import math
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

    __slots__ = ["units", "direction", "share_axis", "max_time_events"]
    # ``direction`` is excluded because flipping minimize<->maximize does not
    # change the recorded numeric values, only their interpretation for
    # Pareto/optimizer plots.  Keeping it in the hash would needlessly wipe
    # over_time history when the user merely retargets the optimizer.
    _hash_exclude = ("direction", "share_axis", "max_time_events")

    def __init__(
        self,
        units="ul",
        direction: OptDir = OptDir.minimize,
        share_axis=True,
        max_time_events=None,
        default=float("nan"),
        **params,
    ):
        Number.__init__(self, **params)
        assert isinstance(units, str)
        self.units = units
        # Defaults to NaN so an *unrecorded* sample (a run that aborts before
        # measuring, or a result var the worker never sets) is treated as
        # missing and dropped by the nan-aware reductions used for regression
        # and aggregation, rather than masquerading as a real 0 measurement.
        # This matches the storage layer, which initialises result arrays with
        # NaN. Callers that want unrecorded samples to read as 0 opt out with
        # ``default=0``.
        self.default = default
        self.direction = direction
        self.share_axis = share_axis
        self.max_time_events = max_time_events

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
        # Stays 0 (=False), unlike ResultFloat's NaN default: False is a
        # meaningful default for a binary outcome, and the binomial-std calc in
        # bench_result_base treats bool means as proportions over a fixed
        # repeat count, which NaN would complicate.
        self.default = default
        self.bounds = (0, 1)  # bools are always between 0 and 1


class ResultVec(param.List):
    """A class to represent fixed size vector result variable"""

    __slots__ = ["units", "direction", "size", "max_time_events"]
    _hash_exclude = ("max_time_events",)

    def __init__(
        self,
        size,
        units="ul",
        direction: OptDir = OptDir.minimize,
        max_time_events=None,
        default=float("nan"),
        **params,
    ):
        param.List.__init__(self, **params)
        self.units = units
        # See ResultFloat.__init__ — defaults to NaN so unrecorded samples are
        # treated as missing; pass ``default=0`` to make them read as 0.
        self.default = default
        self.direction = direction
        self.size = size
        self.max_time_events = max_time_events

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
    __slots__ = ["units", "max_time_events"]
    _hash_exclude = ("max_time_events",)

    def __init__(self, default=None, units="path", max_time_events=None, **params):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)

    def to_container(self):
        """Returns a partial function for creating a FileDownload widget with embedding enabled.  This function is used to create a panel container to represent the ResultPath object"""
        return partial(pn.widgets.FileDownload, embed=True)


class ResultVideo(param.Filename):
    __slots__ = ["units", "max_time_events"]
    _hash_exclude = ("max_time_events",)

    def __init__(self, default=None, units="path", max_time_events=None, **params):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultImage(param.Filename):
    __slots__ = ["units", "max_time_events"]
    _hash_exclude = ("max_time_events",)

    def __init__(self, default=None, units="path", max_time_events=None, **params):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultString(param.String):
    __slots__ = ["units", "max_time_events"]
    _hash_exclude = ("max_time_events",)

    def __init__(self, default=None, units="str", max_time_events=None, **params):
        super().__init__(default=default, **params)
        self.units = units
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultContainer(param.Parameter):
    __slots__ = ["units", "max_time_events"]
    _hash_exclude = ("max_time_events",)

    def __init__(self, default=None, units="container", max_time_events=None, **params):
        super().__init__(default=default, **params)
        self.units = units
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultRerun(ResultContainer):
    """Result type for rerun .rrd spatial visualizations.

    Stores a path to an .rrd file (like ResultContainer) but carries viewer
    sizing metadata and provides a dedicated ``to_container()`` that renders
    the file with the rerun web viewer.

    Usage in a ParametrizedSweep::

        out_rerun = ResultRerun(width=600, height=600)

        def benchmark(self):
            rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta, 1]))
            self.out_rerun = bn.capture_rerun_window(width=600, height=600)
    """

    __slots__ = ["width", "height"]
    # width/height are viewer-pane sizing hints; they do not change the content
    # of the recorded .rrd file, so they must not invalidate the cache.
    _hash_exclude = ("width", "height")

    def __init__(
        self, default=None, units="rerun", width=600, height=600, max_time_events=None, **params
    ):
        super().__init__(default=default, units=units, max_time_events=max_time_events, **params)
        self.width = width
        self.height = height
        # Eagerly create a rerun recording so that rr.log() calls in
        # benchmark() have somewhere to write before capture_rerun_rrd()
        # is called.  Without this, the very first benchmark iteration
        # silently drops its data.
        try:
            from bencher.utils_rerun import _ensure_rerun_init

            _ensure_rerun_init()
        except ImportError:
            pass

    def to_container(self):
        """Return a callable that renders an .rrd file path as a rerun viewer pane."""
        from bencher.utils_rrd import rrd_file_to_pane

        width, height = self.width, self.height
        return partial(rrd_file_to_pane, width=width, height=height)


class ResultReference(param.Parameter):
    """Use this class to save arbitrary objects that are not picklable or native to panel.  You can pass a container callback that takes the object and returns a panel pane to be displayed"""

    __slots__ = ["units", "obj", "container", "max_time_events"]
    _hash_exclude = ("obj", "container", "max_time_events")

    def __init__(
        self,
        obj: Any | None = None,
        container: Callable[Any, pn.pane.panel] | None = None,
        default: Any | None = None,
        units: str = "container",
        max_time_events=None,
        **params,
    ):
        super().__init__(default=default, **params)
        self.units = units
        self.obj = obj
        self.container = container
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultDataSet(param.Parameter):
    __slots__ = ["units", "obj", "max_time_events"]
    _hash_exclude = ("obj", "max_time_events")

    def __init__(
        self,
        obj: Any | None = None,
        default: Any | None = None,
        units: str = "dataset",
        max_time_events=None,
        **params,
    ):
        super().__init__(default=default, **params)
        self.units = units
        self.obj = obj
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultVolume(param.Parameter):
    __slots__ = ["units", "obj", "max_time_events"]
    _hash_exclude = ("obj", "max_time_events")

    def __init__(self, obj=None, default=None, units="container", max_time_events=None, **params):
        super().__init__(default=default, **params)
        self.units = units
        self.obj = obj
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


PANEL_TYPES = (
    ResultPath,
    ResultImage,
    ResultVideo,
    ResultContainer,
    ResultRerun,
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
    ResultRerun,
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
    ResultRerun,
    ResultDataSet,
    ResultReference,
    ResultVolume,
)


# --- Missing / unrecorded-sample representation ----------------------------
#
# Single source of truth for how a *missing* entry of a result variable is
# stored in its typed backing array.  An entry is "missing" when a job never
# wrote it (a run that aborts before measuring, or a result var the worker
# never sets) or when an over_time entry is aged out past ``max_time_events``.
#
# The representation is dtype-specific because xarray/numpy arrays are typed —
# there is no single value that is both storage-valid and reduction-aware
# across every dtype:
#   - numeric types (float/bool/vec, and any future numeric) -> NaN   (float)
#   - index-backed reference types (reference/dataset)       -> -1    (int)
#   - object/file/string types (path/video/image/string/...) -> "NAN" (object)
#
# Both dataset initialisation (``ResultCollector.setup_dataset``) and over_time
# aging (``_null_old_entries``) build their arrays from ``result_missing_fill``,
# and consumers test for missingness with ``result_is_missing`` instead of
# hardcoding ``np.isnan`` / ``== "NAN"`` / ``== -1`` per call site.
_REFERENCE_MISSING_TYPES = (ResultReference, ResultDataSet)
_OBJECT_MISSING_TYPES = (
    ResultPath,
    ResultVideo,
    ResultImage,
    ResultString,
    ResultContainer,
    ResultRerun,
)
# Single-column result types that get a data variable in the dataset. ResultVec
# is handled separately (it expands to one column per element); ResultHmap and
# ResultVolume are stored out-of-band and intentionally get no data variable.
DATA_VAR_RESULT_TYPES = SCALAR_RESULT_TYPES + _REFERENCE_MISSING_TYPES + _OBJECT_MISSING_TYPES


def result_missing_fill(rv) -> tuple[Any, type]:
    """Return the ``(fill_value, numpy_dtype)`` used for missing entries of *rv*."""
    if isinstance(rv, _REFERENCE_MISSING_TYPES):
        return -1, int
    if isinstance(rv, _OBJECT_MISSING_TYPES):
        return "NAN", object
    # ResultFloat / ResultBool / ResultVec / ResultVolume and any future numeric.
    return float("nan"), float


def result_is_missing(rv, value) -> bool:
    """True when *value* is the missing/unrecorded sentinel for *rv*'s storage.

    For NaN-backed (numeric) types, both NaN and ``None`` count as missing — the
    latter is treated as missing intentionally so a value that never reached the
    typed array (e.g. an absent object-index entry) is not mistaken for real
    data. For the ``-1`` / ``"NAN"`` sentinel types, missingness is exact
    equality with the sentinel.
    """
    fill, _ = result_missing_fill(rv)
    if isinstance(fill, float) and math.isnan(fill):
        if value is None:
            return True
        try:
            return math.isnan(float(value))
        except (TypeError, ValueError):
            return False
    return value == fill


class ResultVar(ResultFloat):
    """Deprecated: use ResultFloat instead."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ResultVar is deprecated, use ResultFloat instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
