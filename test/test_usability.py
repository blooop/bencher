"""Tests for usability improvements: subsampling_divisions_to_samples, samples_per_var."""

import math
import unittest

import bencher as bn
from bencher.bench_cfg import BenchRunCfg
from bencher.variables.sweep_base import SUBSAMPLING_DIVISIONS_SAMPLES


class BenchFloat(bn.ParametrizedSweep):
    """Test class using the benchmark() pattern."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    out_sin = bn.ResultFloat(units="v")

    def benchmark(self):
        self.out_sin = math.sin(self.theta)


# ---------- SUBSAMPLING_DIVISIONS_SAMPLES constant ----------


class TestSubsamplingDivisionsSamples(unittest.TestCase):
    def test_exported_from_package(self):
        self.assertIs(bn.SUBSAMPLING_DIVISIONS_SAMPLES, SUBSAMPLING_DIVISIONS_SAMPLES)

    def test_first_entry_is_zero(self):
        self.assertEqual(SUBSAMPLING_DIVISIONS_SAMPLES[0], 0)

    def test_monotonically_increasing(self):
        for i in range(1, len(SUBSAMPLING_DIVISIONS_SAMPLES)):
            self.assertGreater(
                SUBSAMPLING_DIVISIONS_SAMPLES[i], SUBSAMPLING_DIVISIONS_SAMPLES[i - 1]
            )

    def test_level_samples_warns_and_returns_subsampling_divisions_samples(self):
        """LEVEL_SAMPLES emits DeprecationWarning and returns SUBSAMPLING_DIVISIONS_SAMPLES."""
        import bencher.variables.sweep_base as _sb

        with self.assertWarns(DeprecationWarning):
            result = _sb.LEVEL_SAMPLES
        self.assertIs(result, SUBSAMPLING_DIVISIONS_SAMPLES)

        with self.assertWarns(DeprecationWarning):
            bn_result = bn.LEVEL_SAMPLES
        self.assertIs(bn_result, SUBSAMPLING_DIVISIONS_SAMPLES)


# ---------- subsampling_divisions_to_samples ----------


class TestSubsamplingDivisionsToSamples(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(BenchRunCfg.subsampling_divisions_to_samples(1), 1)
        self.assertEqual(BenchRunCfg.subsampling_divisions_to_samples(5), 9)
        self.assertEqual(BenchRunCfg.subsampling_divisions_to_samples(12), 1025)

    def test_invalid_subsampling_divisions_raises(self):
        with self.assertRaises(ValueError):
            BenchRunCfg.subsampling_divisions_to_samples(0)
        with self.assertRaises(ValueError):
            BenchRunCfg.subsampling_divisions_to_samples(99)

    def test_level_to_samples_backward_compat(self):
        """level_to_samples is a backward-compat alias for subsampling_divisions_to_samples."""
        self.assertEqual(
            BenchRunCfg.level_to_samples(5), BenchRunCfg.subsampling_divisions_to_samples(5)
        )


# ---------- with_level backward-compat ----------


class TestWithLevelBackwardCompat(unittest.TestCase):
    def test_bn_with_level_warns_and_delegates(self):
        """bn.with_level emits DeprecationWarning and returns same result as with_subsampling_divisions."""
        arr = list(range(20))
        with self.assertWarns(DeprecationWarning):
            fn = bn.with_level
        self.assertTrue(callable(fn))
        result_alias = fn(arr, 3)
        result_direct = bn.with_subsampling_divisions(arr, 3)
        self.assertEqual(result_alias, result_direct)


# ---------- samples_per_var ----------


class TestSamplesPerVar(unittest.TestCase):
    def test_default_is_none(self):
        cfg = BenchRunCfg()
        self.assertIsNone(cfg.samples_per_var)

    def test_samples_per_var_overrides_subsampling_divisions(self):
        """When samples_per_var is set, the bench should use that count regardless of subsampling_divisions."""
        bench = BenchFloat().to_bench(bn.BenchRunCfg(headless=True, samples_per_var=7))
        result = bench.plot_sweep()
        # The sweep should have used 7 samples for theta
        ds = result.ds
        self.assertEqual(len(ds.coords["theta"]), 7)

    def test_subsampling_divisions_still_works(self):
        bench = BenchFloat().to_bench(bn.BenchRunCfg(headless=True, subsampling_divisions=3))
        result = bench.plot_sweep()
        ds = result.ds
        # subsampling_divisions 3 → 3 samples
        self.assertEqual(len(ds.coords["theta"]), 3)


if __name__ == "__main__":
    unittest.main()
