"""Tests for hash_persistent() determinism across all result variable classes.

These tests ensure that hash_persistent() is deterministic (same result for equivalent
instances) for every Result* class. This is critical for the over_time cache: if a hash
changes across process invocations, historical data can never be found.

Key guarantees enforced by these tests:
- Auto-discovery: any new Result* class is automatically tested (no manual updates needed)
- Slot coverage: every __slots__ entry is either hashed or explicitly in _hash_exclude
- Determinism: two equivalent instances produce the same hash
- Cross-process stability: hash is identical across separate Python processes
- Deepcopy stability: hash survives deepcopy
- Differentiation: different config values produce different hashes
"""

import inspect
import json
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from enum import Enum

import param
import pytest

import bencher.variables.results as results_module
from bencher.variables.results import (
    ResultContainer,
    ResultDataSet,
    ResultImage,
    ResultPath,
    ResultReference,
    ResultString,
    ResultFloat,
    ResultVec,
    ResultVideo,
    ResultVolume,
    _PARAM_MODULES,
)
from bencher.bench_cfg import BenchCfg


def _discover_all_result_classes():
    """Auto-discover all Result* classes in the results module."""
    classes = []
    for name, obj in inspect.getmembers(results_module, inspect.isclass):
        if (
            name.startswith("Result")
            and issubclass(obj, param.Parameter)
            and obj.__module__ == results_module.__name__
        ):
            classes.append(obj)
    return classes


def _make_instance(cls):
    """Create an instance of a result class with sensible defaults."""
    if cls is ResultVec:
        return cls(size=3, units="ul", doc="test")
    return cls(doc="test")


def _collect_mro_slots(cls):
    """Collect all __slots__ from the bencher class hierarchy (matching _hash_slots behavior)."""
    all_slots = []
    seen = set()
    for klass in cls.__mro__:
        if getattr(klass, "__module__", "") in _PARAM_MODULES or klass is object:
            break
        slots = klass.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if slot not in seen:
                seen.add(slot)
                all_slots.append(slot)
    return all_slots


def _collect_mro_excludes(cls):
    """Collect all _hash_exclude entries from the bencher class hierarchy."""
    exclude = set()
    for klass in cls.__mro__:
        if getattr(klass, "__module__", "") in _PARAM_MODULES or klass is object:
            break
        exclude.update(getattr(klass, "_hash_exclude", ()))
    return exclude


# Auto-discovered list — any new Result* class will appear here automatically
ALL_DISCOVERED_CLASSES = _discover_all_result_classes()


class TestSlotCoverage:
    """Verify every __slots__ entry is either hashed or explicitly excluded.

    This catches the case where someone adds a new slot to a class but forgets to
    include it in the hash or _hash_exclude. Without this, the new config attribute
    would be silently ignored by the cache key.
    """

    @pytest.mark.parametrize("cls", ALL_DISCOVERED_CLASSES, ids=lambda c: c.__name__)
    def test_all_slots_accounted_for(self, cls):
        slots = set(_collect_mro_slots(cls))
        exclude = _collect_mro_excludes(cls)
        # _hash_exclude entries must actually be slots
        extra_excludes = exclude - slots
        assert not extra_excludes, (
            f"{cls.__name__}._hash_exclude contains {extra_excludes} "
            f"which are not in __slots__ = {slots}"
        )
        # Verify excluded slots are non-deterministic by checking that instances with
        # different excluded values still produce the same hash
        if exclude:
            r1 = _make_instance(cls)
            r2 = _make_instance(cls)
            for slot in exclude:
                # Set excluded slot to a different value on r2
                setattr(r2, slot, "DIFFERENT_VALUE")
            assert r1.hash_persistent() == r2.hash_persistent(), (
                f"{cls.__name__}: excluded slots {exclude} affected the hash. "
                "If a slot affects the hash, remove it from _hash_exclude."
            )

    @pytest.mark.parametrize("cls", ALL_DISCOVERED_CLASSES, ids=lambda c: c.__name__)
    def test_hashed_slots_affect_hash(self, cls):
        """Every non-excluded slot must actually affect the hash value."""
        all_slots = _collect_mro_slots(cls)
        exclude = _collect_mro_excludes(cls)
        hashed_slots = [s for s in all_slots if s not in exclude]
        if not hashed_slots:
            pytest.skip(f"{cls.__name__} has no hashed slots (uses class name fallback)")
        r1 = _make_instance(cls)
        for slot in hashed_slots:
            r2 = _make_instance(cls)
            original = getattr(r2, slot)
            setattr(r2, slot, "CHANGED_VALUE_FOR_TEST")
            assert r1.hash_persistent() != r2.hash_persistent(), (
                f"{cls.__name__}: changing slot '{slot}' from {original!r} to "
                "'CHANGED_VALUE_FOR_TEST' did not change the hash. "
                "Either add it to _hash_exclude or fix _hash_slots."
            )


class TestHashPersistentDeepcopy:
    """hash_persistent() must be stable across deepcopy."""

    @pytest.mark.parametrize("cls", ALL_DISCOVERED_CLASSES, ids=lambda c: c.__name__)
    def test_deepcopy_stability(self, cls):
        r1 = _make_instance(cls)
        r2 = deepcopy(r1)
        assert r1.hash_persistent() == r2.hash_persistent(), (
            f"{cls.__name__}.hash_persistent() changed after deepcopy"
        )


class TestHashPersistentDifferentiation:
    """Classes with different units values must produce different hashes."""

    @pytest.mark.parametrize(
        "cls,units_a,units_b",
        [
            (ResultImage, "path", "custom"),
            (ResultVideo, "path", "custom"),
            (ResultPath, "path", "custom"),
            (ResultString, "str", "custom"),
            (ResultContainer, "container", "custom"),
            (ResultReference, "container", "custom"),
            (ResultDataSet, "dataset", "custom"),
            (ResultVolume, "container", "custom"),
        ],
        ids=lambda x: x.__name__ if isinstance(x, type) else x,
    )
    def test_different_units_different_hash(self, cls, units_a, units_b):
        r1 = cls(units=units_a, doc="test")
        r2 = cls(units=units_b, doc="test")
        assert r1.hash_persistent() != r2.hash_persistent(), (
            f"{cls.__name__} hashes should differ for units={units_a!r} vs {units_b!r}"
        )

    def test_result_vec_different_size_different_hash(self):
        r1 = ResultVec(size=3, doc="test")
        r2 = ResultVec(size=5, doc="test")
        assert r1.hash_persistent() != r2.hash_persistent(), (
            "ResultVec hashes should differ for size=3 vs size=5"
        )


class TestAutoDiscoverAllResultClasses:
    """Auto-discover all Result* classes and verify they have deterministic hashing.

    This test will AUTOMATICALLY FAIL if a new Result* class is added to
    bencher/variables/results.py without a proper hash_persistent() method.
    No manual test updates are needed — just adding the class triggers the check.
    """

    @pytest.mark.parametrize("cls", ALL_DISCOVERED_CLASSES, ids=lambda c: c.__name__)
    def test_discovered_class_has_hash_persistent(self, cls):
        assert hasattr(cls, "hash_persistent"), (
            f"{cls.__name__} is missing hash_persistent(). "
            "All Result* classes MUST implement hash_persistent() using _hash_slots(self). "
            "See the module docstring in bencher/variables/results.py for the pattern."
        )

    @pytest.mark.parametrize("cls", ALL_DISCOVERED_CLASSES, ids=lambda c: c.__name__)
    def test_discovered_class_hash_is_deterministic(self, cls):
        r1 = _make_instance(cls)
        r2 = _make_instance(cls)
        assert r1.hash_persistent() == r2.hash_persistent(), (
            f"{cls.__name__}.hash_persistent() is non-deterministic! "
            "Two independently constructed instances returned different hashes. "
            "This breaks over_time cache lookups. "
            "Fix: use _hash_slots(self) and add non-deterministic slots to _hash_exclude."
        )


class TestBenchCfgHashStability:
    """BenchCfg.hash_persistent() must be stable when result_vars include previously-buggy types."""

    def test_bench_cfg_with_result_image_stable(self):
        def make_cfg():
            cfg = BenchCfg()
            cfg.bench_name = "test_bench"
            cfg.title = "Test Title"
            cfg.over_time = False
            cfg.repeats = 1
            cfg.tag = ""
            cfg.input_vars = []
            cfg.result_vars = [ResultImage(doc="img")]
            cfg.const_vars = []
            return cfg

        cfg1 = make_cfg()
        cfg2 = make_cfg()
        assert cfg1.hash_persistent(include_repeats=True) == cfg2.hash_persistent(
            include_repeats=True
        ), "BenchCfg hash should be stable across two separate constructions"

    def test_bench_cfg_with_multiple_result_types_stable(self):
        def make_cfg():
            cfg = BenchCfg()
            cfg.bench_name = "multi_bench"
            cfg.title = "Multi"
            cfg.over_time = False
            cfg.repeats = 1
            cfg.tag = ""
            cfg.input_vars = []
            cfg.result_vars = [
                ResultFloat(units="m/s", doc="speed"),
                ResultImage(doc="img"),
                ResultString(doc="label"),
                ResultContainer(doc="cont"),
            ]
            cfg.const_vars = []
            return cfg

        cfg1 = make_cfg()
        cfg2 = make_cfg()
        assert cfg1.hash_persistent(include_repeats=True) == cfg2.hash_persistent(
            include_repeats=True
        )

    def test_bench_cfg_with_object_carrying_result_types_stable(self):
        """Ensure BenchCfg.hash_persistent ignores runtime-only obj fields."""

        def make_cfg(obj_payload):
            cfg = BenchCfg()
            cfg.bench_name = "obj_bench"
            cfg.title = "Object-carrying result types"
            cfg.over_time = False
            cfg.repeats = 1
            cfg.tag = ""
            cfg.input_vars = []
            cfg.result_vars = [
                ResultReference(obj=obj_payload, doc="ref"),
                ResultDataSet(obj=obj_payload, doc="ds"),
                ResultVolume(obj=obj_payload, doc="vol"),
            ]
            cfg.const_vars = []
            return cfg

        # Two separately constructed BenchCfgs with equivalent config but
        # different runtime obj instances should produce the same hash.
        cfg1 = make_cfg({"value": 1})
        cfg2 = make_cfg({"value": 1})
        assert cfg1.hash_persistent(include_repeats=True) == cfg2.hash_persistent(
            include_repeats=True
        ), "BenchCfg hash should be stable with object-carrying result types"

        # Changing the underlying runtime object while keeping the hashed
        # configuration fields the same should not affect the hash.
        cfg3 = make_cfg({"value": 999})
        assert cfg1.hash_persistent(include_repeats=True) == cfg3.hash_persistent(
            include_repeats=True
        ), "BenchCfg hash should not change when only excluded obj fields differ"

    def test_title_change_does_not_affect_hash(self):
        """Changing the display title must not invalidate cached results."""

        def make_cfg(title):
            cfg = BenchCfg()
            cfg.bench_name = "stable_bench"
            cfg.title = title
            cfg.over_time = False
            cfg.repeats = 1
            cfg.tag = ""
            cfg.input_vars = []
            cfg.result_vars = [ResultFloat(units="m/s", doc="speed")]
            cfg.const_vars = []
            return cfg

        cfg_a = make_cfg("Original Title")
        cfg_b = make_cfg("Renamed Title")
        cfg_c = make_cfg(None)
        assert cfg_a.hash_persistent(include_repeats=True) == cfg_b.hash_persistent(
            include_repeats=True
        ), "Renaming the title should not change the hash"
        assert cfg_a.hash_persistent(include_repeats=True) == cfg_c.hash_persistent(
            include_repeats=True
        ), "Setting title to None should not change the hash"
        assert cfg_a.hash_persistent(include_repeats=False) == cfg_b.hash_persistent(
            include_repeats=False
        ), "Renaming the title should not change the sample hash either"


# ---------------------------------------------------------------------------
# Cross-process hash tests — batched for performance
#
# Instead of spawning 2 subprocesses per result class (26 total), we spawn
# exactly 2 subprocesses that each compute ALL hashes and return them as JSON.
# This preserves the cross-process guarantee while cutting ~95s of import overhead.
# ---------------------------------------------------------------------------

# Class names tested for cross-process hash stability — derived from auto-discovery
# so new Result* classes are automatically included.
_CROSS_PROCESS_CLASSES = sorted(cls.__name__ for cls in ALL_DISCOVERED_CLASSES)

_BATCH_HASH_SCRIPT = textwrap.dedent("""\
    import inspect
    import json
    import param
    import bencher.variables.results as results_module
    from bencher.variables.results import ResultVec, ResultFloat, ResultImage
    from bencher.bench_cfg import BenchCfg

    hashes = {}

    # Auto-discover all Result* classes (mirrors parent process discovery)
    for name, cls in inspect.getmembers(results_module, inspect.isclass):
        if (
            name.startswith("Result")
            and issubclass(cls, param.Parameter)
            and cls.__module__ == results_module.__name__
        ):
            instance = cls(size=3, units="ul", doc="test") if cls is ResultVec else cls(doc="test")
            hashes[name] = instance.hash_persistent()

    # BenchCfg composite hash
    cfg = BenchCfg()
    cfg.bench_name = "test_bench"
    cfg.title = "Test"
    cfg.over_time = False
    cfg.repeats = 1
    cfg.tag = ""
    cfg.input_vars = []
    cfg.result_vars = [ResultFloat(units="m/s", doc="speed"), ResultImage(doc="img")]
    cfg.const_vars = []
    hashes["BenchCfg"] = cfg.hash_persistent(include_repeats=True)

    print(json.dumps(hashes))
""")


def _all_hashes_in_subprocess():
    """Spawn a fresh Python process that computes hashes for all result classes + BenchCfg."""
    result = subprocess.run(
        [sys.executable, "-c", _BATCH_HASH_SCRIPT],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"Batch hash subprocess failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


@pytest.fixture(scope="class")
def cross_process_hashes():
    """Run two independent subprocesses and return both hash dicts.

    Scoped to the class so the 2 subprocess invocations are shared across all
    parametrized test methods in TestCrossProcessDeterminism.
    """
    # Thread-safe: each task spawns an independent subprocess with no shared state.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_all_hashes_in_subprocess)
        future_b = executor.submit(_all_hashes_in_subprocess)
        hashes_a = future_a.result()
        hashes_b = future_b.result()
    return hashes_a, hashes_b


class TestCrossProcessDeterminism:
    """Verify hash_persistent() produces identical values across separate processes.

    This is the ultimate test for the over_time cache: process A writes cache with
    a key, process B must compute the same key to find it. In-process tests cannot
    catch bugs where str(obj) includes the memory address, because the address is
    stable within a single process.

    All hashes are computed in a single batched subprocess call per process,
    reducing 26 subprocess invocations to 2 while preserving the cross-process
    guarantee.
    """

    @pytest.mark.parametrize("cls_name", _CROSS_PROCESS_CLASSES)
    def test_hash_stable_across_two_processes(
        self,
        cross_process_hashes,  # pylint: disable=redefined-outer-name
        cls_name,
    ):
        hashes_a, hashes_b = cross_process_hashes
        assert hashes_a[cls_name] == hashes_b[cls_name], (
            f"{cls_name}.hash_persistent() differs across processes: "
            f"{hashes_a[cls_name]!r} != {hashes_b[cls_name]!r}"
        )

    def test_bench_cfg_hash_stable_across_processes(
        self,
        cross_process_hashes,  # pylint: disable=redefined-outer-name
    ):
        """End-to-end: BenchCfg cache key must be identical across processes."""
        hashes_a, hashes_b = cross_process_hashes
        assert hashes_a["BenchCfg"] == hashes_b["BenchCfg"], (
            f"BenchCfg.hash_persistent() differs across processes: "
            f"{hashes_a['BenchCfg']!r} != {hashes_b['BenchCfg']!r}"
        )


# ---------------------------------------------------------------------------
# Sweep-class hash coverage
#
# The benchmark-level and over_time history caches use
# ``BenchCfg.hash_persistent`` which hashes every input/const Sweep variable
# via ``SweepBase.hash_persistent``.  Any field that changes the set of
# sampled values (bounds, sample_values, objects, step) MUST contribute to
# that hash — otherwise a reshaped sweep silently serves stale results.
#
# The sample cache is keyed separately (see bencher.worker_job.WorkerJob)
# by the concrete input tuple + tag, so sweep-hash changes do not affect
# sample-cache reuse across widened/narrowed sweeps.
# ---------------------------------------------------------------------------


class TestSweepHashShapeFields:
    """Changing any shape-affecting sweep field must change the hash."""

    def test_float_sweep_bounds_change_hash(self):
        from bencher.variables.inputs import FloatSweep

        a = FloatSweep(bounds=(0.0, 1.0), samples=10, units="m/s")
        b = FloatSweep(bounds=(0.0, 100.0), samples=10, units="m/s")
        assert a.hash_persistent() != b.hash_persistent(), (
            "FloatSweep bounds must contribute to the hash — otherwise the "
            "benchmark-level cache returns a dataset with stale coordinates."
        )

    def test_float_sweep_sample_values_change_hash(self):
        from bencher.variables.inputs import FloatSweep

        a = FloatSweep(sample_values=[1.0, 2.0, 3.0], units="m/s")
        b = FloatSweep(sample_values=[10.0, 20.0, 30.0], units="m/s")
        assert a.hash_persistent() != b.hash_persistent()

    def test_float_sweep_step_changes_hash(self):
        from bencher.variables.inputs import FloatSweep

        a = FloatSweep(bounds=(0.0, 1.0), samples=10, step=0.1, units="m/s")
        b = FloatSweep(bounds=(0.0, 1.0), samples=10, step=0.01, units="m/s")
        assert a.hash_persistent() != b.hash_persistent()

    def test_int_sweep_bounds_change_hash(self):
        from bencher.variables.inputs import IntSweep

        a = IntSweep(bounds=(0, 10), samples=5, units="ul")
        b = IntSweep(bounds=(0, 1000), samples=5, units="ul")
        assert a.hash_persistent() != b.hash_persistent()

    def test_int_sweep_sample_values_change_hash(self):
        from bencher.variables.inputs import IntSweep

        a = IntSweep(sample_values=[1, 2, 3], units="ul")
        b = IntSweep(sample_values=[10, 20, 30], units="ul")
        assert a.hash_persistent() != b.hash_persistent()

    def test_string_sweep_objects_change_hash(self):
        from bencher.variables.inputs import StringSweep

        a = StringSweep(["a", "b"], units="ul")
        b = StringSweep(["x", "y"], units="ul")
        assert a.hash_persistent() != b.hash_persistent()

    def test_enum_sweep_objects_change_hash(self):
        from bencher.variables.inputs import EnumSweep

        class E1(Enum):
            A = 1
            B = 2

        class E2(Enum):
            X = 10
            Y = 20

        a = EnumSweep(E1, units="ul")
        b = EnumSweep(E2, units="ul")
        assert a.hash_persistent() != b.hash_persistent()

    def test_equivalent_sweeps_produce_same_hash(self):
        """Determinism: two independently constructed equivalent sweeps match."""
        from bencher.variables.inputs import FloatSweep, IntSweep, StringSweep

        assert (
            FloatSweep(bounds=(0.0, 1.0), samples=10, units="m/s").hash_persistent()
            == FloatSweep(bounds=(0.0, 1.0), samples=10, units="m/s").hash_persistent()
        )
        assert (
            IntSweep(bounds=(0, 10), samples=5, units="ul").hash_persistent()
            == IntSweep(bounds=(0, 10), samples=5, units="ul").hash_persistent()
        )
        assert (
            StringSweep(["a", "b"], units="ul").hash_persistent()
            == StringSweep(["a", "b"], units="ul").hash_persistent()
        )

    def test_sweep_selector_uses_bencher_hash_hook(self):
        """Custom objects exposing ``__bencher_hash__`` must route through the hook.

        This is the contract users rely on to get cross-process deterministic
        cache keys when the selector's options are not primitive types.
        """
        from bencher.variables.inputs import SweepSelector

        class Opt:
            def __init__(self, val):
                self.val = val

            def __bencher_hash__(self):
                return ("Opt", self.val)

        a = SweepSelector(objects=[Opt(1), Opt(2)], units="ul")
        b = SweepSelector(objects=[Opt(1), Opt(2)], units="ul")
        assert a.hash_persistent() == b.hash_persistent(), (
            "SweepSelector should treat objects with equal __bencher_hash__ as equal, "
            "even if the instances themselves differ."
        )

        c = SweepSelector(objects=[Opt(10), Opt(20)], units="ul")
        assert a.hash_persistent() != c.hash_persistent(), (
            "Different __bencher_hash__ payloads must produce different sweep hashes."
        )


def _discover_sweep_classes():
    """Auto-discover concrete SweepBase subclasses that can be instantiated for tests."""
    import bencher.variables.inputs as inputs_module
    from bencher.variables.sweep_base import SweepBase

    classes = []
    for _name, obj in inspect.getmembers(inputs_module, inspect.isclass):
        if (
            isinstance(obj, type)
            and issubclass(obj, SweepBase)
            and obj is not SweepBase
            and obj.__module__ == inputs_module.__name__
        ):
            classes.append(obj)
    return classes


class _SweepFixtureEnum(Enum):
    A = 1
    B = 2


def _make_sweep_instance(cls):
    """Instantiate a sweep class with sensible defaults for slot-coverage tests.

    YamlSweep returns None (needs a filesystem path; covered indirectly via
    SweepSelector).  Unknown subclasses also return None so the caller skips them.
    """
    from bencher.variables.inputs import (
        BoolSweep,
        EnumSweep,
        FloatSweep,
        IntSweep,
        StringSweep,
        SweepSelector,
    )

    factories = {
        FloatSweep: lambda: FloatSweep(bounds=(0.0, 1.0), samples=5, units="m/s"),
        IntSweep: lambda: IntSweep(bounds=(0, 10), samples=5, units="ul"),
        StringSweep: lambda: StringSweep(["a", "b", "c"], units="ul"),
        BoolSweep: lambda: BoolSweep(units="ul"),
        EnumSweep: lambda: EnumSweep(_SweepFixtureEnum, units="ul"),
        SweepSelector: lambda: SweepSelector(objects=["a", "b"], units="ul"),
    }
    factory = factories.get(cls)
    return factory() if factory is not None else None


def _collect_sweep_mro_slots(cls):
    """Walk MRO and gather bencher-defined __slots__ entries (dedup, preserving order).

    Stops at the ``param`` framework boundary so we only enforce the
    whitelist discipline on slots that bencher itself introduced —
    ``param``'s own slots (``compute_default_fn``, ``check_on_set``, etc.)
    are framework internals outside our control.
    """
    all_slots = []
    seen = set()
    for klass in cls.__mro__:
        if getattr(klass, "__module__", "") in _PARAM_MODULES or klass is object:
            break
        slots = klass.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if slot not in seen:
                seen.add(slot)
                all_slots.append(slot)
    return all_slots


def _collect_sweep_mro_excludes(cls):
    """Union of ``_sweep_hash_exclude`` across the bencher portion of the MRO."""
    excludes = set()
    for klass in cls.__mro__:
        if getattr(klass, "__module__", "") in _PARAM_MODULES or klass is object:
            break
        excludes.update(getattr(klass, "_sweep_hash_exclude", ()))
    return excludes


_SWEEP_CLASSES = [c for c in _discover_sweep_classes() if _make_sweep_instance(c) is not None]


class TestSweepSlotCoverage:
    """Enforce the whitelist discipline for Sweep classes.

    Every ``__slots__`` entry on a concrete Sweep class must either
    contribute to ``_sweep_identity`` (verified by mutating it and checking
    the hash changes) or be explicitly listed in ``_sweep_hash_exclude`` on
    some ancestor.  This catches the class of bug where someone adds a new
    slot to ``FloatSweep``/``IntSweep``/etc. and forgets to extend the
    identity tuple — the new field would otherwise silently not contribute,
    and the benchmark-level cache would collide on it.
    """

    @pytest.mark.parametrize("cls", _SWEEP_CLASSES, ids=lambda c: c.__name__)
    def test_each_slot_is_hashed_or_excluded(self, cls):
        slots = _collect_sweep_mro_slots(cls)
        excludes = _collect_sweep_mro_excludes(cls)

        # ``_sweep_hash_exclude`` entries must actually name real slots —
        # otherwise the annotation is a typo silently ignored by the test.
        stale_excludes = excludes - set(slots)
        assert not stale_excludes, (
            f"{cls.__name__}._sweep_hash_exclude names {stale_excludes} "
            f"which are not in __slots__={slots}"
        )

        instance = _make_sweep_instance(cls)
        if instance is None:
            pytest.skip(f"No fixture for {cls.__name__}")

        baseline = instance.hash_persistent()

        for slot in slots:
            if slot in excludes:
                # Excluded slot: mutating it must NOT change the hash.
                mutated = _make_sweep_instance(cls)
                try:
                    original = getattr(mutated, slot)
                    sentinel = (
                        "__sentinel_value__" if original != "__sentinel_value__" else "__other__"
                    )
                    object.__setattr__(mutated, slot, sentinel)
                except (AttributeError, TypeError, ValueError):
                    continue  # can't mutate cleanly; excluded by virtue of being unsettable
                assert mutated.hash_persistent() == baseline, (
                    f"{cls.__name__}: slot {slot!r} is in _sweep_hash_exclude "
                    f"but mutating it changed the hash. Either remove it from "
                    f"_sweep_hash_exclude or fix _sweep_identity."
                )
            else:
                # Non-excluded slot: changing it MUST change the hash.  We
                # try a handful of sentinel values so we are resilient to
                # param-level type checks.
                candidates = [None, 0, 1, -1, "__sweep_hash_probe__", (0, 0), (1, 2), [1, 2, 3]]
                mutated_hashes = set()
                for candidate in candidates:
                    mutated = _make_sweep_instance(cls)
                    original = getattr(mutated, slot)
                    if candidate == original:
                        continue
                    try:
                        object.__setattr__(mutated, slot, candidate)
                    except (AttributeError, TypeError, ValueError):
                        continue
                    try:
                        mutated_hashes.add(mutated.hash_persistent())
                    except (TypeError, AttributeError, ValueError):
                        continue
                assert any(h != baseline for h in mutated_hashes), (
                    f"{cls.__name__}: slot {slot!r} is NOT in _sweep_hash_exclude "
                    f"and mutating it never changed the hash. Either add it to "
                    f"_sweep_hash_exclude (if it is display/runtime-only) or "
                    f"extend _sweep_identity so it contributes to the hash."
                )


# ---------------------------------------------------------------------------
# Golden hash regression
#
# Any change that intentionally alters what ``BenchCfg.hash_persistent``
# composes requires:
#   1. bumping ``CACHE_VERSION`` in bencher/cache_management.py
#   2. updating the ``GOLDEN_BENCH_CFG_HASH_*`` values below
#   3. documenting the break in CHANGELOG.md
#
# This test exists so incidental drift (e.g. someone adding a new field to
# the hash tuple) fails CI loudly instead of silently stranding every
# on-disk benchmark-level and over_time entry in the field.
# ---------------------------------------------------------------------------

GOLDEN_BENCH_CFG_HASH_INCLUDING_REPEATS = "afbbadba143168305abeaab3e2e53ea9c429c2a5"
GOLDEN_BENCH_CFG_HASH_EXCLUDING_REPEATS = "6093b4560b17af4dab2f14f5609b7b945499df63"


def _build_golden_bench_cfg():
    from bencher.variables.inputs import FloatSweep, IntSweep, StringSweep

    cfg = BenchCfg()
    cfg.bench_name = "golden_bench"
    cfg.title = "should not affect hash"
    cfg.over_time = False
    cfg.repeats = 3
    cfg.tag = "golden_tag"
    cfg.input_vars = [
        FloatSweep(bounds=(0.0, 1.0), samples=5, units="m/s"),
        IntSweep(bounds=(0, 10), samples=4, units="count"),
        StringSweep(["a", "b", "c"], units="label"),
    ]
    cfg.result_vars = [ResultFloat(units="kg", doc="mass")]
    cfg.const_vars = [(FloatSweep(bounds=(0.0, 1.0), samples=5, units="m/s"), 0.5)]
    return cfg


class TestGoldenBenchCfgHash:
    """Byte-exact regression check on the BenchCfg hash composition.

    If this test fails and you did not intend to invalidate every on-disk
    cache, something has drifted.  If you DID intend to change the hash
    (e.g. including a new field, excluding a cosmetic one), update the
    constants above AND bump ``CACHE_VERSION`` so existing installations
    clear their caches cleanly.
    """

    def test_golden_hash_with_repeats(self):
        cfg = _build_golden_bench_cfg()
        assert cfg.hash_persistent(include_repeats=True) == (
            GOLDEN_BENCH_CFG_HASH_INCLUDING_REPEATS
        ), (
            "BenchCfg hash drifted. See the module docstring for the "
            "procedure to intentionally update this value."
        )

    def test_golden_hash_without_repeats(self):
        cfg = _build_golden_bench_cfg()
        assert cfg.hash_persistent(include_repeats=False) == (
            GOLDEN_BENCH_CFG_HASH_EXCLUDING_REPEATS
        )

    def test_title_change_does_not_affect_golden_hash(self):
        cfg = _build_golden_bench_cfg()
        cfg.title = "a completely different title"
        assert cfg.hash_persistent(include_repeats=True) == GOLDEN_BENCH_CFG_HASH_INCLUDING_REPEATS

    def test_cache_version_participates_in_hash(self):
        """Bumping CACHE_VERSION must change the hash atomically."""
        import bencher.bench_cfg as bench_cfg_mod

        cfg = _build_golden_bench_cfg()
        original = cfg.hash_persistent(include_repeats=True)
        saved_version = bench_cfg_mod.CACHE_VERSION
        try:
            bench_cfg_mod.CACHE_VERSION = saved_version + "_test_probe"
            bumped = cfg.hash_persistent(include_repeats=True)
        finally:
            bench_cfg_mod.CACHE_VERSION = saved_version
        assert bumped != original, (
            "CACHE_VERSION must participate in BenchCfg.hash_persistent so "
            "bumping it atomically invalidates every cache key."
        )

    def test_sweep_bounds_change_bench_hash(self):
        """End-to-end: widening a FloatSweep invalidates the benchmark-level cache."""
        from bencher.variables.inputs import FloatSweep

        cfg_a = _build_golden_bench_cfg()
        cfg_b = _build_golden_bench_cfg()
        cfg_b.input_vars[0] = FloatSweep(bounds=(0.0, 1000.0), samples=5, units="m/s")
        assert cfg_a.hash_persistent(include_repeats=True) != cfg_b.hash_persistent(
            include_repeats=True
        ), (
            "Changing FloatSweep bounds must change the BenchCfg hash — "
            "otherwise the benchmark-level cache returns stale coordinates."
        )

    def test_result_direction_does_not_change_bench_hash(self):
        """Flipping minimize<->maximize must not invalidate history."""
        from bencher.variables.results import OptDir

        cfg_a = _build_golden_bench_cfg()
        cfg_b = _build_golden_bench_cfg()
        cfg_b.result_vars = [ResultFloat(units="kg", direction=OptDir.maximize, doc="mass")]
        assert cfg_a.hash_persistent(include_repeats=True) == cfg_b.hash_persistent(
            include_repeats=True
        ), (
            "ResultFloat.direction is interpretive metadata and must not "
            "contribute to the cache key."
        )
