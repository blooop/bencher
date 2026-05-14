"""Tests for usability improvements: fidelity_to_samples, samples_per_var."""

import math
import unittest

import bencher as bn
from bencher.bench_cfg import BenchRunCfg
from bencher.variables.sweep_base import FIDELITY_SAMPLES


class BenchFloat(bn.ParametrizedSweep):
    """Test class using the benchmark() pattern."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    out_sin = bn.ResultVar(units="v")

    def benchmark(self):
        self.out_sin = math.sin(self.theta)


# ---------- FIDELITY_SAMPLES constant ----------


class TestFidelitySamples(unittest.TestCase):
    def test_exported_from_package(self):
        self.assertIs(bn.FIDELITY_SAMPLES, FIDELITY_SAMPLES)

    def test_first_entry_is_zero(self):
        self.assertEqual(FIDELITY_SAMPLES[0], 0)

    def test_monotonically_increasing(self):
        for i in range(1, len(FIDELITY_SAMPLES)):
            self.assertGreater(FIDELITY_SAMPLES[i], FIDELITY_SAMPLES[i - 1])

    def test_level_samples_warns_and_returns_fidelity_samples(self):
        """LEVEL_SAMPLES emits DeprecationWarning and returns FIDELITY_SAMPLES."""
        import bencher.variables.sweep_base as _sb

        with self.assertWarns(DeprecationWarning):
            result = _sb.LEVEL_SAMPLES
        self.assertIs(result, FIDELITY_SAMPLES)

        with self.assertWarns(DeprecationWarning):
            bn_result = bn.LEVEL_SAMPLES
        self.assertIs(bn_result, FIDELITY_SAMPLES)


# ---------- fidelity_to_samples ----------


class TestFidelityToSamples(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(BenchRunCfg.fidelity_to_samples(1), 1)
        self.assertEqual(BenchRunCfg.fidelity_to_samples(5), 9)
        self.assertEqual(BenchRunCfg.fidelity_to_samples(12), 1025)

    def test_invalid_fidelity_raises(self):
        with self.assertRaises(ValueError):
            BenchRunCfg.fidelity_to_samples(0)
        with self.assertRaises(ValueError):
            BenchRunCfg.fidelity_to_samples(99)

    def test_level_to_samples_backward_compat(self):
        """level_to_samples is a backward-compat alias for fidelity_to_samples."""
        self.assertEqual(BenchRunCfg.level_to_samples(5), BenchRunCfg.fidelity_to_samples(5))


# ---------- samples_per_var ----------


class TestSamplesPerVar(unittest.TestCase):
    def test_default_is_none(self):
        cfg = BenchRunCfg()
        self.assertIsNone(cfg.samples_per_var)

    def test_samples_per_var_overrides_fidelity(self):
        """When samples_per_var is set, the bench should use that count regardless of fidelity."""
        bench = BenchFloat().to_bench(bn.BenchRunCfg(headless=True, samples_per_var=7))
        result = bench.plot_sweep()
        # The sweep should have used 7 samples for theta
        ds = result.ds
        self.assertEqual(len(ds.coords["theta"]), 7)

    def test_fidelity_still_works(self):
        bench = BenchFloat().to_bench(bn.BenchRunCfg(headless=True, fidelity=3))
        result = bench.plot_sweep()
        ds = result.ds
        # fidelity 3 → 3 samples
        self.assertEqual(len(ds.coords["theta"]), 3)


if __name__ == "__main__":
    unittest.main()
