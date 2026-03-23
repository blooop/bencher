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
    ResultVar,
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
                ResultVar(units="m/s", doc="speed"),
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
    from bencher.variables.results import ResultVec, ResultVar, ResultImage
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
    cfg.result_vars = [ResultVar(units="m/s", doc="speed"), ResultImage(doc="img")]
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
