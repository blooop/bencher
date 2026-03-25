"""Tests for usability improvements: compute method, level_to_samples, samples_per_var, factories."""

import math
import unittest

import bencher as bn
from bencher.bench_cfg import BenchRunCfg
from bencher.variables.sweep_base import LEVEL_SAMPLES


# ---------- compute() method auto-wrapping ----------


class ComputeFloat(bn.ParametrizedSweep):
    """Test class using the new compute() pattern."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    out_sin = bn.ResultVar(units="v")

    def compute(self, **kwargs):
        self.out_sin = math.sin(self.theta)


class ClassicFloat(bn.ParametrizedSweep):
    """Same benchmark using the classic __call__ pattern."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    out_sin = bn.ResultVar(units="v")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__(**kwargs)


class TestComputeMethod(unittest.TestCase):
    def test_compute_returns_dict(self):
        """compute()-based class returns a result dict from __call__."""
        obj = ComputeFloat()
        result = obj(theta=1.0)
        self.assertIsInstance(result, dict)
        self.assertIn("out_sin", result)
        self.assertAlmostEqual(result["out_sin"], math.sin(1.0))

    def test_compute_matches_classic(self):
        """compute()-based class produces the same results as classic __call__."""
        for theta in [0.0, 0.5, 1.0, math.pi / 2, math.pi]:
            r_new = ComputeFloat()(theta=theta)
            r_old = ClassicFloat()(theta=theta)
            self.assertAlmostEqual(r_new["out_sin"], r_old["out_sin"])

    def test_compute_works_with_bench(self):
        """compute()-based class works end-to-end with Bench."""
        bench = ComputeFloat().to_bench(bn.BenchRunCfg(headless=True))
        bench.plot_sweep()

    def test_classic_call_still_works(self):
        """Classic __call__ pattern is unaffected by __init_subclass__."""
        obj = ClassicFloat()
        result = obj(theta=1.0)
        self.assertIn("out_sin", result)


# ---------- LEVEL_SAMPLES constant ----------


class TestLevelSamples(unittest.TestCase):
    def test_exported_from_package(self):
        self.assertIs(bn.LEVEL_SAMPLES, LEVEL_SAMPLES)

    def test_first_entry_is_zero(self):
        self.assertEqual(LEVEL_SAMPLES[0], 0)

    def test_monotonically_increasing(self):
        for i in range(1, len(LEVEL_SAMPLES)):
            self.assertGreater(LEVEL_SAMPLES[i], LEVEL_SAMPLES[i - 1])


# ---------- level_to_samples ----------


class TestLevelToSamples(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(BenchRunCfg.level_to_samples(1), 1)
        self.assertEqual(BenchRunCfg.level_to_samples(5), 9)
        self.assertEqual(BenchRunCfg.level_to_samples(12), 1025)

    def test_invalid_level_raises(self):
        with self.assertRaises(ValueError):
            BenchRunCfg.level_to_samples(0)
        with self.assertRaises(ValueError):
            BenchRunCfg.level_to_samples(99)


# ---------- samples_per_var ----------


class TestSamplesPerVar(unittest.TestCase):
    def test_default_is_none(self):
        cfg = BenchRunCfg()
        self.assertIsNone(cfg.samples_per_var)

    def test_samples_per_var_overrides_level(self):
        """When samples_per_var is set, the bench should use that count regardless of level."""
        bench = ComputeFloat().to_bench(bn.BenchRunCfg(headless=True, samples_per_var=7))
        result = bench.plot_sweep()
        # The sweep should have used 7 samples for theta
        ds = result.ds
        self.assertEqual(len(ds.coords["theta"]), 7)

    def test_level_still_works(self):
        bench = ComputeFloat().to_bench(bn.BenchRunCfg(headless=True, level=3))
        result = bench.plot_sweep()
        ds = result.ds
        # level 3 → 3 samples
        self.assertEqual(len(ds.coords["theta"]), 3)


# ---------- Factory classmethods ----------


class TestFactories(unittest.TestCase):
    def test_for_time_series(self):
        cfg = BenchRunCfg.for_time_series(time_event="v1.0")
        self.assertTrue(cfg.over_time)
        self.assertTrue(cfg.cache_samples)
        self.assertEqual(cfg.time_event, "v1.0")

    def test_for_time_series_allows_overrides(self):
        cfg = BenchRunCfg.for_time_series(time_event="v2.0", repeats=3)
        self.assertEqual(cfg.repeats, 3)
        self.assertTrue(cfg.over_time)

    def test_for_ci(self):
        cfg = BenchRunCfg.for_ci()
        self.assertTrue(cfg.headless)
        self.assertTrue(cfg.cache_samples)
        self.assertFalse(cfg.show)
        self.assertFalse(cfg.over_time)

    def test_for_ci_with_time_event(self):
        cfg = BenchRunCfg.for_ci(time_event="PR-42")
        self.assertTrue(cfg.over_time)
        self.assertEqual(cfg.time_event, "PR-42")


if __name__ == "__main__":
    unittest.main()
