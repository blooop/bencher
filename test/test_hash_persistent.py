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
import subprocess
import sys
import textwrap
from copy import deepcopy

import param
import pytest

import bencher.variables.results as results_module
from bencher.variables.results import (
    ALL_RESULT_TYPES,
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


# Auto-discovered list — any new Result* class will appear here automatically
ALL_DISCOVERED_CLASSES = _discover_all_result_classes()

# Manually curated list for cross-checking
ALL_HASHABLE_CLASSES = list(ALL_RESULT_TYPES) + [ResultVolume]


class TestSlotCoverage:
    """Verify every __slots__ entry is either hashed or explicitly excluded.

    This catches the case where someone adds a new slot to a class but forgets to
    include it in the hash or _hash_exclude. Without this, the new config attribute
    would be silently ignored by the cache key.
    """

    @pytest.mark.parametrize("cls", ALL_DISCOVERED_CLASSES, ids=lambda c: c.__name__)
    def test_all_slots_accounted_for(self, cls):
        slots = set(cls.__dict__.get("__slots__", ()))
        exclude = set(getattr(cls, "_hash_exclude", ()))
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
        slots = list(cls.__dict__.get("__slots__", ()))
        exclude = set(getattr(cls, "_hash_exclude", ()))
        hashed_slots = [s for s in slots if s not in exclude]
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


class TestHashPersistentDeterminism:
    """Two independently constructed instances with the same parameters must hash identically."""

    @pytest.mark.parametrize("cls", ALL_HASHABLE_CLASSES, ids=lambda c: c.__name__)
    def test_same_hash_for_identical_instances(self, cls):
        r1 = _make_instance(cls)
        r2 = _make_instance(cls)
        assert r1.hash_persistent() == r2.hash_persistent(), (
            f"{cls.__name__}.hash_persistent() differs between two identical instances"
        )


class TestHashPersistentDeepcopy:
    """hash_persistent() must be stable across deepcopy."""

    @pytest.mark.parametrize("cls", ALL_HASHABLE_CLASSES, ids=lambda c: c.__name__)
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


class TestHashPersistentCompleteness:
    """Every type in ALL_RESULT_TYPES must have a hash_persistent method."""

    @pytest.mark.parametrize("cls", list(ALL_RESULT_TYPES), ids=lambda c: c.__name__)
    def test_has_hash_persistent(self, cls):
        assert hasattr(cls, "hash_persistent"), (
            f"{cls.__name__} in ALL_RESULT_TYPES is missing hash_persistent()"
        )
        instance = _make_instance(cls)
        h = instance.hash_persistent()
        assert isinstance(h, str) and len(h) > 0


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


class TestSpecificVerification:
    """Explicit verification from the task description."""

    def test_result_image_triple_equality(self):
        r1 = ResultImage(doc="test")
        r2 = ResultImage(doc="test")
        r3 = deepcopy(r1)
        assert r1.hash_persistent() == r2.hash_persistent() == r3.hash_persistent()

    def test_result_string_triple_equality(self):
        r1 = ResultString(doc="test")
        r2 = ResultString(doc="test")
        r3 = deepcopy(r1)
        assert r1.hash_persistent() == r2.hash_persistent() == r3.hash_persistent()

    def test_result_video_triple_equality(self):
        r1 = ResultVideo(doc="test")
        r2 = ResultVideo(doc="test")
        r3 = deepcopy(r1)
        assert r1.hash_persistent() == r2.hash_persistent() == r3.hash_persistent()


# Script template for cross-process tests. Each subprocess imports the class,
# constructs an instance, and prints its hash. The parent compares hashes from
# two independent processes to verify they match.
_SUBPROCESS_HASH_SCRIPT = textwrap.dedent("""\
    from bencher.variables.results import {cls_name}
    {extra}
    r = {cls_name}({args})
    print(r.hash_persistent())
""")


def _hash_in_subprocess(cls_name, args="doc='test'", extra=""):
    """Spawn a fresh Python process and return the hash_persistent() value."""
    script = _SUBPROCESS_HASH_SCRIPT.format(
        cls_name=cls_name,
        args=args,
        extra=extra,
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"Subprocess failed for {cls_name}:\n{result.stderr}"
    return result.stdout.strip()


class TestCrossProcessDeterminism:
    """Verify hash_persistent() produces identical values across separate processes.

    This is the ultimate test for the over_time cache: process A writes cache with
    a key, process B must compute the same key to find it. In-process tests cannot
    catch bugs where str(obj) includes the memory address, because the address is
    stable within a single process.
    """

    @pytest.mark.parametrize(
        "cls_name,args",
        [
            ("ResultVar", "units='ul', doc='test'"),
            ("ResultBool", "units='ratio', doc='test'"),
            ("ResultVec", "size=3, units='ul', doc='test'"),
            ("ResultHmap", "doc='test'"),
            ("ResultPath", "doc='test'"),
            ("ResultVideo", "doc='test'"),
            ("ResultImage", "doc='test'"),
            ("ResultString", "doc='test'"),
            ("ResultContainer", "doc='test'"),
            ("ResultReference", "doc='test'"),
            ("ResultDataSet", "doc='test'"),
            ("ResultVolume", "doc='test'"),
        ],
    )
    def test_hash_stable_across_two_processes(self, cls_name, args):
        hash_a = _hash_in_subprocess(cls_name, args)
        hash_b = _hash_in_subprocess(cls_name, args)
        assert hash_a == hash_b, (
            f"{cls_name}.hash_persistent() differs across processes: {hash_a!r} != {hash_b!r}"
        )

    def test_bench_cfg_hash_stable_across_processes(self):
        """End-to-end: BenchCfg cache key must be identical across processes."""
        script = textwrap.dedent("""\
            from bencher.variables.results import ResultImage, ResultVar
            from bencher.bench_cfg import BenchCfg
            cfg = BenchCfg()
            cfg.bench_name = "test_bench"
            cfg.title = "Test"
            cfg.over_time = False
            cfg.repeats = 1
            cfg.tag = ""
            cfg.input_vars = []
            cfg.result_vars = [ResultVar(units="m/s", doc="speed"), ResultImage(doc="img")]
            cfg.const_vars = []
            print(cfg.hash_persistent(include_repeats=True))
        """)
        hashes = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert result.returncode == 0, f"Subprocess failed:\n{result.stderr}"
            hashes.append(result.stdout.strip())
        assert hashes[0] == hashes[1], (
            f"BenchCfg.hash_persistent() differs across processes: {hashes[0]!r} != {hashes[1]!r}"
        )
