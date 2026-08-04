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
import numbers
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from enum import auto
from functools import partial
from typing import Any

import holoviews as hv
import panel as pn
import param
from param import Number
from strenum import StrEnum

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

    The Parameter *name* is also included: history columns and regression baselines are
    keyed by name, so two same-typed result vars with different names are different
    measurements and must not share a cache identity. Unbound instances hash name=None,
    which is deterministic.
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
    return hash_sha1((cls.__name__, instance.name) + values)


class OptDir(StrEnum):
    minimize = auto()
    maximize = auto()
    none = auto()  # If none this var will not appear in pareto plots


class ResultFloat(Number):
    """A class to represent continuous float result variables and the desired optimisation direction.

    For boolean (success/failure) outcomes, use ``ResultBool`` instead — it locks
    bounds to [0, 1] and produces correct boolean-style plots.
    """

    __slots__ = ["units", "direction", "share_axis", "max_time_events", "meaning_version"]
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
        meaning_version=1,
        **params,
    ):
        Number.__init__(self, **params)
        assert isinstance(units, str)
        self.units = units
        # The sanctioned way to declare "same name, new semantics": bump
        # meaning_version when the quantity this metric measures changes
        # (e.g. success redefined from reported to physically verified).
        # It is part of the column identity, so the bump cleanly restarts
        # this column's over_time history and regression baseline while
        # every other column's history continues. Without a bump, a
        # redefinition would silently splice two different quantities into
        # one trend line.
        self.meaning_version = meaning_version
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

    def __init__(
        self, units="ratio", direction: OptDir = OptDir.minimize, default=float("nan"), **params
    ):
        super().__init__(units=units, direction=direction, allow_None=True, **params)
        # Defaults to NaN like ResultFloat (see ResultFloat.__init__): an
        # *unrecorded* repeat is "missing", not a recorded failure, so it is
        # dropped from the success proportion rather than counted as False. The
        # binomial-std calc in bench_result_base divides p*(1-p) by the per-cell
        # count of valid (non-NaN) repeats, so missing repeats don't understate
        # the SE. A worker that wants a crash/abort to count as a failure must
        # record False on its failure path; callers wanting the old False-fill
        # opt out with ``default=0``.
        self.default = default
        self.bounds = (0, 1)  # bools are always between 0 and 1

    def _validate_bounds(self, val, bounds, inclusive_bounds):
        # NaN is the sentinel for an unrecorded ("missing") sample — see
        # ResultFloat.__init__.  It lies outside the [0, 1] bounds, so param's
        # bounds check would reject both ``default=float("nan")`` (re-validated
        # whenever a subclass overrides the Parameter) and any NaN *value* set
        # at runtime to mark a sample missing.  Treat NaN as always valid so a
        # result bool can use the same missing sentinel as ResultFloat, while
        # still rejecting genuinely out-of-range values.  Use math.isnan rather
        # than ``isinstance(val, float)`` so numpy NaN scalars (e.g. np.float32)
        # are also recognised; non-numeric values (None, str) raise here and
        # fall through to the normal bounds check.
        try:
            if math.isnan(val):
                return
        except (TypeError, ValueError):
            pass
        super()._validate_bounds(val, bounds, inclusive_bounds)


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
    """Deprecated: use ResultContainer or ResultReference with a declared container instead.

    A class to represent a holomap return type. Its data lives out-of-band in
    ``bench_res.hmaps`` rather than in the canonical result dataset, so it cannot
    participate in the A6 grammar-of-ND-data migration; removal is scheduled for
    a later phase of that migration.

    Note: this class has no __slots__, so _hash_slots hashes only the class name.
    Every ResultHmap instance produces the same hash. This is intentional — there are
    no configuration attributes that would differentiate instances. If a slot is added
    in the future, _hash_slots will automatically include it.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ResultHmap is deprecated and will be removed in a later phase of the A6 "
            "grammar-of-nd-data migration; use ResultContainer or ResultReference with "
            "a declared container= instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)

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
    """A path to a file the benchmark produced.

    Renders as a download widget by default. Declare ``container=`` a callable
    taking the path and returning anything panel can display to render the file's
    *contents* instead — a CSV as a chart, a JSON as a tree — and it wins over the
    download widget. See :class:`ResultDataSet` for the contract the callback has
    to satisfy.
    """

    __slots__ = ["units", "container", "max_time_events"]
    _hash_exclude = ("container", "max_time_events")

    def __init__(
        self,
        default=None,
        units="path",
        container: Callable[[Any], Any] | None = None,
        max_time_events=None,
        **params,
    ):
        super().__init__(default=default, check_exists=False, **params)
        self.units = units
        self.container = container
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
    """Text the benchmark produced.

    Renders as plain text by default. Declare ``container=`` a callable taking the
    string and returning anything panel can display to render it as something
    richer — Markdown, syntax-highlighted code, a parsed structure. See
    :class:`ResultDataSet` for the contract the callback has to satisfy.
    """

    __slots__ = ["units", "container", "max_time_events"]
    _hash_exclude = ("container", "max_time_events")

    def __init__(
        self,
        default=None,
        units="str",
        container: Callable[[Any], Any] | None = None,
        max_time_events=None,
        **params,
    ):
        super().__init__(default=default, **params)
        self.units = units
        self.container = container
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultContainer(param.Parameter):
    """Embeddable HTML/panel content the benchmark produced.

    Handed to panel as-is by default. Declare ``container=`` a callable taking the
    stored value and returning anything panel can display to wrap or transform it
    first. See :class:`ResultDataSet` for the contract the callback has to satisfy.
    """

    __slots__ = ["units", "container", "max_time_events"]
    _hash_exclude = ("container", "max_time_events")

    def __init__(
        self,
        default=None,
        units="container",
        container: Callable[[Any], Any] | None = None,
        max_time_events=None,
        **params,
    ):
        super().__init__(default=default, **params)
        self.units = units
        self.container = container
        self.max_time_events = max_time_events

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return _hash_slots(self)


class ResultRerun(ResultContainer):
    """Result type for rerun .rrd spatial visualizations.

    Stores a path to an .rrd file (like ResultContainer) but carries viewer
    sizing metadata and provides a dedicated ``to_container()`` that renders
    the file with the rerun web viewer. A ``ComposableContainerRerun`` can also
    be assigned directly; result collection materializes it to one .rrd file
    before caching.

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
    """Use this class to save arbitrary objects that are not picklable or native to panel.

    ``container`` is a callback taking the stored object and returning something panel
    can display. It can be attached to a single sample inside ``benchmark()`` or
    declared once on the class, exactly as for :class:`ResultDataSet`::

        plot = ResultReference(container=my_renderer)   # my_renderer(obj) -> pane

    The callback receives only the object — no plot kwargs — so single-argument
    callables are safe, and one renderer works for both this and a ``ResultDataSet``.

    This is the documented same-process escape hatch: the stored object stays live,
    is stripped by both the result cache write and the collect/render split, and is
    never load-bearing for the core rendering algebra. Use :class:`ResultDataSet`
    when the payload should survive process boundaries.
    """

    __slots__ = ["units", "obj", "container", "max_time_events"]
    _hash_exclude = ("obj", "container", "max_time_events")

    def __init__(
        self,
        obj: Any | None = None,
        container: Callable[[Any], Any] | None = None,
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
    """An arbitrary picklable data payload stored for each benchmark sample.

    The payload may be a DataFrame, xarray object, mapping, sequence, custom
    dataclass, or any other object that can travel through the configured result
    cache. Bencher stores and retrieves it without interpreting its type.

    Payloads are materialized into the cache's content-addressed blob store at
    collect time (parquet for DataFrames, netCDF for xarray objects, pickle
    otherwise — see :mod:`bencher.blob_store`); the dataset cell stores the blob
    path, so any process sharing the cache filesystem can render any sample,
    including over_time history points.

    ``container`` is an optional renderer taking the stored object and returning
    something Panel can display. Declare it once on the class and every sample
    renders through it, in ``result_vars`` order, alongside the other results::

        payload = ResultDataSet(container=render_payload)

        def benchmark(self):
            self.payload = ResultDataSet(measure())

    Per-sample overrides are honoured too (``ResultDataSet(data, container=...)``
    inside ``benchmark()``), and an explicit ``container=`` passed to a renderer
    beats both.  The callback receives only the object — no plot kwargs — so
    single-argument callables are safe.

    A declared renderer travels with ``BenchCfg`` into the result cache and
    through the collect/render split, so it has to be picklable: a module-level
    function or a callable object, not a lambda or a local function. Use
    ``ResultReference`` instead when the payload itself is not picklable.
    """

    __slots__ = ["units", "obj", "container", "max_time_events"]
    _hash_exclude = ("obj", "container", "max_time_events")

    def __init__(
        self,
        obj: Any | None = None,
        container: Callable[[Any], Any] | None = None,
        default: Any | None = None,
        units: str = "dataset",
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


# --- Result-type registry (plan 23 P4) --------------------------------------
#
# Single source of truth for how every Result* class is classified and stored.
# It replaces nine hand-maintained tuples (PANEL_TYPES, SCALAR_RESULT_TYPES,
# XARRAY_MULTIDIM_RESULT_TYPES, ALL_RESULT_TYPES, RESULT_KIND_ORDER,
# _REFERENCE_MISSING_TYPES, _OBJECT_MISSING_TYPES, DATA_VAR_RESULT_TYPES and
# result_collector's _MEDIA_RESULT_TYPES) that each had their own silent
# failure mode when a new class missed one of them. The original names are
# all still exported, derived from the registry, so call sites are unchanged.
# Adding a Result* class without a spec fails CI (test/test_result_missing.py)
# and is refused at sweep-declaration time (parametrised_sweep.py).


class ResultKind(StrEnum):
    """Coarse, serializable classification of a result variable.

    The values feed the A2 plot-selection signatures, so they must stay
    stable strings. Explicit values rather than ``auto()``: ``strenum``'s
    ``auto()`` yields the member *name* verbatim, which would silently change
    these to uppercase (plan 23 D4)."""

    BOOL = "bool"
    FLOAT = "float"
    VEC = "vec"
    IMAGE = "image"
    VIDEO = "video"
    PATH = "path"
    STRING = "string"
    DATASET = "dataset"
    RERUN = "rerun"
    CONTAINER = "container"
    HMAP = "hmap"
    REFERENCE = "reference"


@dataclass(frozen=True)
class ResultSpec:
    """Storage and classification contract for one Result* class.

    Attributes:
        kind: Coarse kind name for plot-selection signatures (A2).
        missing_fill: Value written for a missing/unrecorded sample.
        fill_dtype: Numpy dtype of the backing array (float | object | int).
        missing_sentinels: Exact-equality sentinel values accepted as
            "missing" on READ. This can be wider than ``{missing_fill}``
            because missingness is not a pure function of the fill:
            ``ResultDataSet`` accepts both its cell generations (``"NAN"``
            blob references from plan 22 onwards, ``-1`` indices before)
            permanently. NaN/``None`` missingness is dtype-generic and handled
            in :func:`result_is_missing`, not listed here (NaN has no useful
            equality semantics in a set).
        is_scalar: Continuous/boolean scalar metric (regression, optimization).
        is_panel: Rendered through the panel pathway rather than holoviews.
        is_media: Cell values reference media files on disk that over_time
            aging must delete when entries age out.
        is_data_var: Gets a single data variable (column) in the dataset.
            ``ResultVec`` expands to one column per element and ``ResultHmap``
            is stored out-of-band, so neither is a data var.
        multidim: Member of the xarray multidim store family
            (``XARRAY_MULTIDIM_RESULT_TYPES``).
        reference_backed: Cell stores an ``object_index`` index
            (``ResultReference`` only).
    """

    kind: ResultKind
    missing_fill: Any
    fill_dtype: type
    missing_sentinels: frozenset
    is_scalar: bool
    is_panel: bool
    is_media: bool
    is_data_var: bool
    multidim: bool
    reference_backed: bool


_NAN = float("nan")

# Insertion order is the isinstance-resolution order: most-derived first
# (ResultBool subclasses ResultFloat; ResultRerun subclasses ResultContainer).
# A test pins that no key precedes one of its own subclasses.
RESULT_SPECS: dict[type, ResultSpec] = {
    ResultBool: ResultSpec(
        kind=ResultKind.BOOL,
        missing_fill=_NAN,
        fill_dtype=float,
        missing_sentinels=frozenset(),
        is_scalar=True,
        is_panel=False,
        is_media=False,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultFloat: ResultSpec(
        kind=ResultKind.FLOAT,
        missing_fill=_NAN,
        fill_dtype=float,
        missing_sentinels=frozenset(),
        is_scalar=True,
        is_panel=False,
        is_media=False,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultVec: ResultSpec(
        kind=ResultKind.VEC,
        missing_fill=_NAN,
        fill_dtype=float,
        missing_sentinels=frozenset(),
        is_scalar=False,
        is_panel=False,
        is_media=False,
        is_data_var=False,
        multidim=False,
        reference_backed=False,
    ),
    ResultImage: ResultSpec(
        kind=ResultKind.IMAGE,
        missing_fill="NAN",
        fill_dtype=object,
        missing_sentinels=frozenset({"NAN"}),
        is_scalar=False,
        is_panel=True,
        is_media=True,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultVideo: ResultSpec(
        kind=ResultKind.VIDEO,
        missing_fill="NAN",
        fill_dtype=object,
        missing_sentinels=frozenset({"NAN"}),
        is_scalar=False,
        is_panel=True,
        is_media=True,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultPath: ResultSpec(
        kind=ResultKind.PATH,
        missing_fill="NAN",
        fill_dtype=object,
        missing_sentinels=frozenset({"NAN"}),
        is_scalar=False,
        is_panel=True,
        is_media=True,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultString: ResultSpec(
        kind=ResultKind.STRING,
        missing_fill="NAN",
        fill_dtype=object,
        missing_sentinels=frozenset({"NAN"}),
        is_scalar=False,
        is_panel=True,
        is_media=False,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultDataSet: ResultSpec(
        kind=ResultKind.DATASET,
        missing_fill="NAN",
        fill_dtype=object,
        # Dual-generation compatibility (plan 22): "NAN" blob-path cells and
        # legacy -1 index cells are both missing, permanently. The float
        # promotion (-1.0) and NaN/None acceptance live in
        # _dataset_cell_is_missing — do NOT collapse that into this set.
        missing_sentinels=frozenset({"NAN", -1}),
        is_scalar=False,
        is_panel=True,
        is_media=False,
        is_data_var=True,
        multidim=False,
        reference_backed=False,
    ),
    ResultRerun: ResultSpec(
        kind=ResultKind.RERUN,
        missing_fill="NAN",
        fill_dtype=object,
        missing_sentinels=frozenset({"NAN"}),
        is_scalar=False,
        is_panel=True,
        is_media=True,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultContainer: ResultSpec(
        kind=ResultKind.CONTAINER,
        missing_fill="NAN",
        fill_dtype=object,
        missing_sentinels=frozenset({"NAN"}),
        is_scalar=False,
        is_panel=True,
        is_media=True,
        is_data_var=True,
        multidim=True,
        reference_backed=False,
    ),
    ResultHmap: ResultSpec(
        kind=ResultKind.HMAP,
        missing_fill=_NAN,
        fill_dtype=float,
        missing_sentinels=frozenset(),
        is_scalar=False,
        is_panel=False,
        is_media=False,
        is_data_var=False,
        multidim=False,
        reference_backed=False,
    ),
    ResultReference: ResultSpec(
        kind=ResultKind.REFERENCE,
        missing_fill=-1,
        fill_dtype=int,
        missing_sentinels=frozenset({-1}),
        is_scalar=False,
        is_panel=True,
        is_media=False,
        is_data_var=True,
        multidim=False,
        reference_backed=True,
    ),
}


def result_spec(result_var) -> ResultSpec | None:
    """Spec for a result-variable instance, resolved most-derived-first.

    Returns ``None`` for parameters that are not registered result types.
    Deprecated subclasses absent from the registry (``ResultVar``) resolve to
    their base class's spec via isinstance."""
    for cls, spec in RESULT_SPECS.items():
        if isinstance(result_var, cls):
            return spec
    return None


def _spec_types(predicate) -> tuple[type, ...]:
    """The registry keys whose spec satisfies *predicate*, in registry order."""
    return tuple(cls for cls, spec in RESULT_SPECS.items() if predicate(spec))


# The nine pre-registry names, derived. Every consumer is an isinstance()
# check, so membership (not tuple order) is the behavioral contract; only
# RESULT_KIND_ORDER is order-sensitive and reproduces its original order
# exactly. A transitional test pins each against its pre-migration literal.
PANEL_TYPES = _spec_types(lambda s: s.is_panel)

SCALAR_RESULT_TYPES = _spec_types(lambda s: s.is_scalar)

XARRAY_MULTIDIM_RESULT_TYPES = _spec_types(lambda s: s.multidim)

ALL_RESULT_TYPES = tuple(RESULT_SPECS)

# Most-derived first: kind classification takes the first isinstance match.
RESULT_KIND_ORDER = tuple((cls, spec.kind.value) for cls, spec in RESULT_SPECS.items())

# Result types whose cell names a file this variable alone owns, so aging the
# cell out of the over_time history deletes the file too (see
# ``result_collector._null_old_entries``).
#
# ``ResultDataSet`` is deliberately not media (``is_media=False``), even though
# its cells are paths as well: blob-store files are content-addressed, so one
# file may back cells at other time points, in other result variables, or in
# another benchmark sharing the cache — identical payloads deduplicate to a
# single path by design, and the aging path sees only the variable it is aging.
# Deleting the file there would strand every other cell still holding that
# path. Aging therefore only writes the sentinel; reclaiming blob storage
# belongs to ``bencher.cache_management``, which is the layer that can see the
# whole cache and tell a dropped payload from a shared one.
_MEDIA_RESULT_TYPES = _spec_types(lambda s: s.is_media)


def result_kind(result_var) -> str:
    """Classify a result variable into a coarse, serializable kind name used by
    plot-selection signatures (A2)."""
    spec = result_spec(result_var)
    return spec.kind.value if spec is not None else "unknown"


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
#   - index-backed reference types (reference)               -> -1    (int)
#   - object/file/string types (path/video/image/string/...) -> "NAN" (object)
#
# ResultDataSet cells are blob references since plan 22 (grammar phase 1), so its
# fill is the blob-family "NAN"; results collected before that change store -1
# int indices, and ``result_is_missing`` accepts BOTH generations permanently —
# a mixed-generation over_time history contains cells of each kind.
#
# Both dataset initialisation (``ResultCollector.setup_dataset``) and over_time
# aging (``_null_old_entries``) build their arrays from ``result_missing_fill``,
# and consumers test for missingness with ``result_is_missing`` instead of
# hardcoding ``np.isnan`` / ``== "NAN"`` / ``== -1`` per call site.
_REFERENCE_MISSING_TYPES = _spec_types(lambda s: s.reference_backed)
_OBJECT_MISSING_TYPES = _spec_types(lambda s: s.fill_dtype is object)
# Single-column result types that get a data variable in the dataset. ResultVec
# is handled separately (it expands to one column per element); ResultHmap is
# stored out-of-band and intentionally gets no data variable.
DATA_VAR_RESULT_TYPES = _spec_types(lambda s: s.is_data_var)


def result_missing_fill(rv) -> tuple[Any, type]:
    """Return the ``(fill_value, numpy_dtype)`` used for missing entries of *rv*.

    Read from the ResultSpec registry; an unregistered parameter (or a future
    numeric result type before registration) falls back to the NaN family,
    matching the pre-registry behavior."""
    spec = result_spec(rv)
    if spec is None:
        return float("nan"), float
    return spec.missing_fill, spec.fill_dtype


def _dataset_cell_is_missing(value) -> bool:
    """Missingness for a ``ResultDataSet`` cell, across both sentinel generations.

    ``"NAN"`` (blob-path cells, plan 22 onwards) and ``-1`` (index-backed cells
    collected before it, including the float ``-1.0`` an over_time concat can
    promote an int column to) are both missing, permanently — a mixed-generation
    history holds cells of each kind.  NaN/``None`` also count as missing so an
    unrepaired concat fill is never handed to ``load_blob`` or a
    ``dataset_list`` lookup as data.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value == "NAN"
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        as_float = float(value)
        return math.isnan(as_float) or as_float == -1.0
    return False


def result_is_missing(rv, value) -> bool:
    """True when *value* is the missing/unrecorded sentinel for *rv*'s storage.

    For NaN-backed (numeric) types, both NaN and ``None`` count as missing — the
    latter is treated as missing intentionally so a value that never reached the
    typed array (e.g. an absent object-index entry) is not mistaken for real
    data. Non-numeric values (strings, lists, …) are never missing for a
    numeric type: they cannot be the NaN sentinel, so no float coercion is
    attempted (the *string* ``"nan"`` is real data, not a missing marker). For
    the ``-1`` / ``"NAN"`` sentinel types, missingness is exact equality with
    the sentinel.

    ``ResultDataSet`` accepts BOTH its sentinel generations, permanently — see
    :func:`_dataset_cell_is_missing`.
    """
    if isinstance(rv, ResultDataSet):
        return _dataset_cell_is_missing(value)
    fill, _ = result_missing_fill(rv)
    if isinstance(fill, float) and math.isnan(fill):
        if value is None:
            return True
        # numbers.Real covers python ints/floats/bools and numpy scalars
        # (numpy registers them with the numbers ABC tower).
        if isinstance(value, numbers.Real):
            return math.isnan(float(value))
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


# Result* classes deliberately absent from RESULT_SPECS, so the completeness
# test can tell "exempt" from "forgotten". An exempt class must resolve to a
# registered base class via isinstance (result_spec falls through to it) and
# has never been a member of any registry tuple.
RESULT_SPEC_EXEMPT: dict[type, str] = {
    ResultVar: "deprecated alias of ResultFloat; instances resolve to ResultFloat's spec",
}
