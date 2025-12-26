"""Tests for the bench_cfg package."""

import unittest
from datetime import datetime

from bencher.bench_cfg import (
    BenchPlotSrvCfg,
    CacheCfg,
    ExecutionCfg,
    DisplayCfg,
    VisualizationCfg,
    TimeCfg,
    BenchRunCfg,
    BenchCfg,
)


class TestSubConfigClasses(unittest.TestCase):
    """Test individual sub-configuration classes."""

    def test_cache_cfg_defaults(self):
        cfg = CacheCfg()
        self.assertFalse(cfg.cache_results)
        self.assertFalse(cfg.cache_samples)
        self.assertFalse(cfg.only_plot)

    def test_execution_cfg_defaults(self):
        cfg = ExecutionCfg()
        self.assertEqual(cfg.repeats, 1)
        self.assertEqual(cfg.level, 0)
        self.assertFalse(cfg.nightly)

    def test_display_cfg_defaults(self):
        cfg = DisplayCfg()
        self.assertTrue(cfg.print_bench_inputs)
        self.assertTrue(cfg.print_bench_results)
        self.assertFalse(cfg.print_pandas)

    def test_visualization_cfg_defaults(self):
        cfg = VisualizationCfg()
        self.assertTrue(cfg.auto_plot)
        self.assertFalse(cfg.use_holoview)
        self.assertIsNone(cfg.plot_size)

    def test_time_cfg_defaults(self):
        cfg = TimeCfg()
        self.assertFalse(cfg.over_time)
        self.assertEqual(cfg.run_tag, "")
        self.assertIsInstance(cfg.run_date, datetime)

    def test_server_cfg_defaults(self):
        cfg = BenchPlotSrvCfg()
        self.assertIsNone(cfg.port)
        self.assertTrue(cfg.show)


class TestBenchRunCfgComposition(unittest.TestCase):
    """Test BenchRunCfg composition and delegation."""

    def test_sub_configs_created(self):
        """Sub-configs are created on init."""
        cfg = BenchRunCfg()
        self.assertIsInstance(cfg.cache, CacheCfg)
        self.assertIsInstance(cfg.execution, ExecutionCfg)
        self.assertIsInstance(cfg.display, DisplayCfg)
        self.assertIsInstance(cfg.visualization, VisualizationCfg)
        self.assertIsInstance(cfg.time, TimeCfg)
        self.assertIsInstance(cfg.server, BenchPlotSrvCfg)

    def test_flat_parameter_access(self):
        """Parameters accessible directly on BenchRunCfg."""
        cfg = BenchRunCfg()
        # Should not raise
        _ = cfg.cache_results
        _ = cfg.repeats
        _ = cfg.auto_plot
        _ = cfg.over_time
        _ = cfg.port

    def test_flat_parameter_init(self):
        """Flat parameters can be set via constructor."""
        cfg = BenchRunCfg(cache_results=True, repeats=5, auto_plot=False)
        self.assertTrue(cfg.cache_results)
        self.assertEqual(cfg.repeats, 5)
        self.assertFalse(cfg.auto_plot)

    def test_flat_parameter_setter(self):
        """Flat parameters can be set via assignment."""
        cfg = BenchRunCfg()
        cfg.cache_results = True
        cfg.repeats = 10
        self.assertTrue(cfg.cache_results)
        self.assertEqual(cfg.repeats, 10)

    def test_grouped_access(self):
        """Parameters accessible via sub-config."""
        cfg = BenchRunCfg(cache_results=True, repeats=5)
        self.assertTrue(cfg.cache.cache_results)
        self.assertEqual(cfg.execution.repeats, 5)

    def test_flat_and_grouped_sync(self):
        """Flat and grouped access point to same value."""
        cfg = BenchRunCfg()
        cfg.cache_results = True
        self.assertTrue(cfg.cache.cache_results)

        cfg.cache.cache_samples = True
        self.assertTrue(cfg.cache_samples)

    def test_deep_copy(self):
        """deep() creates independent copy."""
        cfg = BenchRunCfg(repeats=5)
        copy = cfg.deep()
        copy.repeats = 10
        self.assertEqual(cfg.repeats, 5)
        self.assertEqual(copy.repeats, 10)


class TestBenchCfgInheritance(unittest.TestCase):
    """Test BenchCfg inherits delegation from BenchRunCfg."""

    def test_inherits_flat_access(self):
        """BenchCfg has flat parameter access."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            cache_results=True,
            repeats=3,
        )
        self.assertTrue(cfg.cache_results)
        self.assertEqual(cfg.repeats, 3)

    def test_over_time_works(self):
        """over_time parameter works correctly."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            over_time=True,
        )
        self.assertTrue(cfg.over_time)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of imports."""

    def test_import_from_bench_cfg_module(self):
        """Classes importable from bencher.bench_cfg."""
        from bencher.bench_cfg import DimsCfg

        self.assertIsNotNone(BenchRunCfg)
        self.assertIsNotNone(BenchCfg)
        self.assertIsNotNone(DimsCfg)

    def test_import_from_bencher(self):
        """Classes importable from bencher."""
        from bencher import BenchRunCfg, BenchCfg

        self.assertIsNotNone(BenchRunCfg)
        self.assertIsNotNone(BenchCfg)

    def test_import_new_sub_configs(self):
        """New sub-config classes are importable."""
        from bencher.bench_cfg import CacheCfg, ExecutionCfg, DisplayCfg

        self.assertIsNotNone(CacheCfg)
        self.assertIsNotNone(ExecutionCfg)
        self.assertIsNotNone(DisplayCfg)


if __name__ == "__main__":
    unittest.main()
