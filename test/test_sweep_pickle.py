"""Tests for pickle/deepcopy/multiprocessing safety of all sweep types.

These tests guard against regressions like the ListProxy pickle failure
(PR #854) where SweepSelector.values() returned a param ListProxy instead
of a plain list, breaking pickle serialization under multiprocessing.
"""

from __future__ import annotations

import pickle
import copy
from concurrent.futures import ProcessPoolExecutor
from enum import auto
from pathlib import Path

import pytest
from strenum import StrEnum

import bencher as bn
from bencher.variables.inputs import (
    IntSweep,
    FloatSweep,
    StringSweep,
    EnumSweep,
    BoolSweep,
    YamlSweep,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

YAML_DICT = Path(__file__).resolve().parent.parent / "bencher" / "example" / "yaml_sweep_dict.yaml"


class Color(StrEnum):
    RED = auto()
    GREEN = auto()
    BLUE = auto()


def _build_sweeps():
    """Return a dict of sweep_name -> sweep instance covering every type."""
    sweeps = {
        "int": IntSweep(default=2, bounds=(0, 10)),
        "int_sample_values": IntSweep(sample_values=[1, 3, 7]),
        "float": FloatSweep(default=0.5, bounds=(0.0, 1.0), samples=5),
        "float_step": FloatSweep(default=0.0, bounds=(0.0, 1.0), step=0.25),
        "float_sample_values": FloatSweep(sample_values=[0.1, 0.5, 0.9]),
        "string": StringSweep(["alpha", "beta", "gamma", "delta"]),
        "enum": EnumSweep(Color),
        "enum_list": EnumSweep([Color.RED, Color.BLUE]),
        "bool_true": BoolSweep(default=True),
        "bool_false": BoolSweep(default=False),
    }
    if YAML_DICT.exists():
        sweeps["yaml"] = YamlSweep(YAML_DICT)
    return sweeps


def _pickle_roundtrip(obj):
    """Serialize and deserialize via pickle (protocol 5, highest common)."""
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    return pickle.loads(data)  # noqa: S301


def _identity(x):
    """Trivial function for multiprocessing – must be module-level for pickling."""
    return x


def _values_equal(a, b):
    """Compare two values() results, handling numpy arrays."""
    return str(a) == str(b)


# ---------------------------------------------------------------------------
# 1. SweepSelector.values() returns a plain list, never a ListProxy
# ---------------------------------------------------------------------------

# SweepSelector subclasses (StringSweep, EnumSweep, BoolSweep, YamlSweep)
# must return a plain list from values(), not a param ListProxy.
# IntSweep and FloatSweep may return plain lists or numpy arrays — that's fine.
SELECTOR_SWEEP_NAMES = {"string", "enum", "enum_list", "bool_true", "bool_false", "yaml"}


class TestValuesReturnType:
    """SweepSelector.values() must return a plain list, not a ListProxy."""

    def _assert_plain_list(self, vals, context=""):
        assert type(vals) is list, f"Expected plain list, got {type(vals).__name__} ({context})"

    def test_raw_selector_values(self):
        for name, sw in _build_sweeps().items():
            if name in SELECTOR_SWEEP_NAMES:
                self._assert_plain_list(sw.values(), f"{name}.values()")

    def test_with_samples_selector_values(self):
        for name, sw in _build_sweeps().items():
            if name in SELECTOR_SWEEP_NAMES:
                mutated = sw.with_samples(2)
                self._assert_plain_list(mutated.values(), f"{name}.with_samples(2).values()")

    def test_with_level_values(self):
        """After with_level(), all sweep types must return a plain list."""
        for name, sw in _build_sweeps().items():
            for level in (1, 2, 3, 4):
                mutated = sw.with_level(level)
                self._assert_plain_list(mutated.values(), f"{name}.with_level({level}).values()")

    def test_with_sample_values_returns_plain_list(self):
        sw = StringSweep(["a", "b", "c"])
        mutated = sw.with_sample_values(["x", "y"])
        self._assert_plain_list(mutated.values(), "StringSweep.with_sample_values().values()")


# ---------------------------------------------------------------------------
# 2. Pickle round-trip for raw sweeps
# ---------------------------------------------------------------------------


class TestPickleRaw:
    """Every sweep type must survive pickle round-trip in its default state."""

    def test_pickle_all_types(self):
        for name, sw in _build_sweeps().items():
            restored = _pickle_roundtrip(sw)
            assert _values_equal(restored.values(), sw.values()), (
                f"Pickle round-trip failed for {name}"
            )


# ---------------------------------------------------------------------------
# 3. Pickle round-trip after mutations (with_level, with_samples, etc.)
# ---------------------------------------------------------------------------


class TestPickleAfterMutation:
    """Sweeps must remain picklable after every mutation method."""

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_pickle_after_with_level(self, level):
        for name, sw in _build_sweeps().items():
            mutated = sw.with_level(level)
            restored = _pickle_roundtrip(mutated)
            assert restored.values() == mutated.values(), (
                f"Pickle failed for {name}.with_level({level})"
            )

    def test_pickle_after_with_samples(self):
        for name, sw in _build_sweeps().items():
            mutated = sw.with_samples(2)
            restored = _pickle_roundtrip(mutated)
            assert _values_equal(restored.values(), mutated.values()), (
                f"Pickle failed for {name}.with_samples(2)"
            )

    def test_pickle_after_with_sample_values(self):
        sw = StringSweep(["a", "b", "c", "d"])
        mutated = sw.with_sample_values(["b", "d"])
        restored = _pickle_roundtrip(mutated)
        assert restored.values() == ["b", "d"]

    def test_pickle_after_with_sample_values_enum(self):
        sw = EnumSweep(Color)
        mutated = sw.with_sample_values([Color.RED, Color.BLUE])
        restored = _pickle_roundtrip(mutated)
        assert restored.values() == [Color.RED, Color.BLUE]

    def test_pickle_after_with_sample_values_bool(self):
        sw = BoolSweep()
        mutated = sw.with_sample_values([False])
        restored = _pickle_roundtrip(mutated)
        assert restored.values() == [False]

    def test_pickle_after_with_bounds(self):
        for cls, kwargs in [
            (FloatSweep, {"bounds": (0, 10), "samples": 5}),
            (IntSweep, {"bounds": (0, 100)}),
        ]:
            sw = cls(**kwargs)
            mutated = sw.with_bounds(2, 8, samples=3)
            restored = _pickle_roundtrip(mutated)
            assert str(restored.values()) == str(mutated.values())

    def test_pickle_after_callable_api(self):
        sw = StringSweep(["x", "y", "z"])
        mutated = sw(["x", "z"])
        restored = _pickle_roundtrip(mutated)
        assert restored.values() == ["x", "z"]


# ---------------------------------------------------------------------------
# 4. Deepcopy round-trip (the mechanism used by with_* methods internally)
# ---------------------------------------------------------------------------


class TestDeepcopy:
    """deepcopy must work cleanly for all sweep types and mutations."""

    def test_deepcopy_raw(self):
        for name, sw in _build_sweeps().items():
            cloned = copy.deepcopy(sw)
            assert _values_equal(cloned.values(), sw.values()), f"Deepcopy failed for {name}"

    def test_deepcopy_after_with_level(self):
        for name, sw in _build_sweeps().items():
            mutated = sw.with_level(3)
            cloned = copy.deepcopy(mutated)
            assert cloned.values() == mutated.values(), (
                f"Deepcopy after with_level failed for {name}"
            )

    def test_deepcopy_after_with_samples(self):
        for name, sw in _build_sweeps().items():
            mutated = sw.with_samples(2)
            cloned = copy.deepcopy(mutated)
            assert _values_equal(cloned.values(), mutated.values()), (
                f"Deepcopy after with_samples failed for {name}"
            )

    def test_deepcopy_independence(self):
        """Modifying the clone must not affect the original."""
        sw = StringSweep(["a", "b", "c"])
        cloned = copy.deepcopy(sw)
        cloned_level = cloned.with_level(1)
        assert sw.values() == ["a", "b", "c"]
        assert cloned_level.values() == ["a"]


# ---------------------------------------------------------------------------
# 5. Multiprocessing end-to-end (the actual failure mode from PR #854)
# ---------------------------------------------------------------------------


def _pickle_in_subprocess(sweep_bytes):
    """Unpickle a sweep inside a subprocess and return its values().

    This mimics what ProcessPoolExecutor does: serialize to child, run, return.
    """
    sw = pickle.loads(sweep_bytes)  # noqa: S301
    return sw.values()


class TestMultiprocessing:
    """Sweeps must survive being sent to a subprocess via ProcessPoolExecutor."""

    def _roundtrip_via_pool(self, sw):
        """Send a sweep to a worker process and get values() back."""
        payload = pickle.dumps(sw, protocol=pickle.HIGHEST_PROTOCOL)
        with ProcessPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_pickle_in_subprocess, payload)
            return future.result(timeout=30)

    def test_multiprocessing_raw(self):
        for name, sw in _build_sweeps().items():
            result = self._roundtrip_via_pool(sw)
            assert _values_equal(result, sw.values()), (
                f"Multiprocessing round-trip failed for {name}"
            )

    @pytest.mark.parametrize("level", [1, 2, 3, 4])
    def test_multiprocessing_after_with_level(self, level):
        """This is the exact scenario that PR #854 fixed."""
        for name, sw in _build_sweeps().items():
            mutated = sw.with_level(level)
            result = self._roundtrip_via_pool(mutated)
            assert result == mutated.values(), (
                f"Multiprocessing failed for {name}.with_level({level})"
            )

    def test_multiprocessing_after_with_samples(self):
        for name, sw in _build_sweeps().items():
            mutated = sw.with_samples(2)
            result = self._roundtrip_via_pool(mutated)
            assert _values_equal(result, mutated.values()), (
                f"Multiprocessing failed for {name}.with_samples(2)"
            )

    def test_multiprocessing_after_with_sample_values(self):
        sw = StringSweep(["a", "b", "c"])
        mutated = sw.with_sample_values(["a", "c"])
        result = self._roundtrip_via_pool(mutated)
        assert result == ["a", "c"]

    def test_multiprocessing_selector_with_level_string(self):
        """Explicit regression test: StringSweep.with_level() must be picklable."""
        sw = StringSweep(["a", "b", "c"])
        mutated = sw.with_level(4)
        result = self._roundtrip_via_pool(mutated)
        assert result == mutated.values()

    def test_multiprocessing_selector_with_level_enum(self):
        """Explicit regression test: EnumSweep.with_level() must be picklable."""
        sw = EnumSweep(Color)
        mutated = sw.with_level(3)
        result = self._roundtrip_via_pool(mutated)
        assert result == mutated.values()

    def test_multiprocessing_selector_with_level_bool(self):
        """Explicit regression test: BoolSweep.with_level() must be picklable."""
        sw = BoolSweep()
        mutated = sw.with_level(2)
        result = self._roundtrip_via_pool(mutated)
        assert result == mutated.values()


# ---------------------------------------------------------------------------
# 6. Pickle inside container (simulates BenchCfg holding sweeps)
# ---------------------------------------------------------------------------


class TestPickleInContainer:
    """Sweeps inside dicts/lists/dataclass-like containers must pickle cleanly.

    This mirrors the real failure: BenchCfg holds sweep objects as part of
    its input_vars, and the whole thing gets pickled for multiprocessing.
    """

    def test_dict_of_mutated_sweeps(self):
        container = {}
        for name, sw in _build_sweeps().items():
            container[name] = sw.with_level(3)

        restored = _pickle_roundtrip(container)
        for name in container:
            assert restored[name].values() == container[name].values(), (
                f"Pickle in dict failed for {name}"
            )

    def test_list_of_mutated_sweeps(self):
        sweeps = [sw.with_level(3) for sw in _build_sweeps().values()]
        restored = _pickle_roundtrip(sweeps)
        for orig, rest in zip(sweeps, restored):
            assert rest.values() == orig.values()

    def test_nested_structure(self):
        """Deeply nested structure containing sweeps must pickle."""
        sw = StringSweep(["x", "y", "z"]).with_level(2)
        container = {"config": {"input_vars": [sw], "metadata": {"name": "test"}}}
        restored = _pickle_roundtrip(container)
        assert restored["config"]["input_vars"][0].values() == sw.values()


# ---------------------------------------------------------------------------
# 7. Chained mutations (with_level -> deepcopy -> pickle, etc.)
# ---------------------------------------------------------------------------


class TestChainedMutations:
    """Multiple mutations chained together must remain serializable."""

    def test_with_level_then_deepcopy_then_pickle(self):
        sw = StringSweep(["a", "b", "c", "d"]).with_level(3)
        cloned = copy.deepcopy(sw)
        restored = _pickle_roundtrip(cloned)
        assert restored.values() == sw.values()

    def test_with_samples_then_with_level_then_pickle(self):
        sw = IntSweep(bounds=(0, 100))
        mutated = sw.with_samples(20).with_level(3)
        restored = _pickle_roundtrip(mutated)
        assert restored.values() == mutated.values()

    def test_with_level_then_with_sample_values_then_pickle(self):
        sw = EnumSweep(Color).with_level(2)
        mutated = sw.with_sample_values([Color.GREEN])
        restored = _pickle_roundtrip(mutated)
        assert restored.values() == [Color.GREEN]

    def test_double_with_level(self):
        """Applying with_level twice must not corrupt internal state."""
        sw = StringSweep(["a", "b", "c", "d"])
        lvl2 = sw.with_level(2)
        lvl3 = lvl2.with_level(3)
        restored = _pickle_roundtrip(lvl3)
        assert restored.values() == lvl3.values()


# ---------------------------------------------------------------------------
# 8. Pickle protocol coverage
# ---------------------------------------------------------------------------


class TestPickleProtocols:
    """Sweeps must work with all pickle protocols, not just the highest."""

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_all_protocols_string_sweep_with_level(self, protocol):
        sw = StringSweep(["a", "b", "c"]).with_level(3)
        data = pickle.dumps(sw, protocol=protocol)
        restored = pickle.loads(data)  # noqa: S301
        assert restored.values() == sw.values()

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_all_protocols_enum_sweep_with_level(self, protocol):
        sw = EnumSweep(Color).with_level(2)
        data = pickle.dumps(sw, protocol=protocol)
        restored = pickle.loads(data)  # noqa: S301
        assert restored.values() == sw.values()

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_all_protocols_bool_sweep_with_level(self, protocol):
        sw = BoolSweep().with_level(2)
        data = pickle.dumps(sw, protocol=protocol)
        restored = pickle.loads(data)  # noqa: S301
        assert restored.values() == sw.values()


# ---------------------------------------------------------------------------
# 9. ParametrizedSweep with SweepSelector fields (integration)
# ---------------------------------------------------------------------------


class SampleConfig(bn.ParametrizedSweep):
    color = EnumSweep(Color)
    label = StringSweep(["fast", "medium", "slow"])
    enabled = BoolSweep(default=True)
    count = IntSweep(default=5, bounds=(1, 10))
    ratio = FloatSweep(default=0.5, bounds=(0.0, 1.0), samples=5)


class TestParametrizedSweepPickle:
    """A ParametrizedSweep instance containing selector sweeps must pickle."""

    def test_instance_pickles(self):
        cfg = SampleConfig()
        restored = _pickle_roundtrip(cfg)
        assert restored.color == cfg.color
        assert restored.label == cfg.label
        assert restored.enabled == cfg.enabled

    def test_class_params_pickle_after_with_level(self):
        """Each class-level param, after with_level(), must pickle."""
        for p_name in ("color", "label", "enabled", "count", "ratio"):
            param = SampleConfig.param[p_name]  # pylint: disable=unsubscriptable-object
            mutated = param.with_level(2)
            restored = _pickle_roundtrip(mutated)
            assert restored.values() == mutated.values(), (
                f"ParametrizedSweep.param.{p_name}.with_level(2) failed pickle"
            )

    def test_input_vars_list_pickles(self):
        """Simulates what Bench does: collects input_vars as with_level'd sweeps."""
        input_vars = [
            SampleConfig.param.color.with_level(2),
            SampleConfig.param.label.with_level(3),
            SampleConfig.param.enabled.with_level(2),
            SampleConfig.param.count.with_level(3),
            SampleConfig.param.ratio.with_level(3),
        ]
        restored = _pickle_roundtrip(input_vars)
        for orig, rest in zip(input_vars, restored):
            assert rest.values() == orig.values()
