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

    def test_grouped_parameter_access(self):
        """Parameters accessible via sub-configs on BenchRunCfg."""
        cfg = BenchRunCfg()
        # Should not raise
        _ = cfg.cache.cache_results
        _ = cfg.execution.repeats
        _ = cfg.visualization.auto_plot
        _ = cfg.time.over_time
        _ = cfg.server.port

    def test_flat_attribute_access_raises(self):
        """Flat attribute access is no longer supported and raises AttributeError."""
        cfg = BenchRunCfg()
        with self.assertRaises(AttributeError):
            _ = cfg.cache_results
        with self.assertRaises(AttributeError):
            _ = cfg.repeats
        with self.assertRaises(AttributeError):
            _ = cfg.auto_plot
        with self.assertRaises(AttributeError):
            _ = cfg.over_time

    def test_sub_config_init(self):
        """Sub-config parameters can be set via constructor."""
        cfg = BenchRunCfg(
            cache=CacheCfg(cache_results=True),
            execution=ExecutionCfg(repeats=5),
            visualization=VisualizationCfg(auto_plot=False),
        )
        self.assertTrue(cfg.cache.cache_results)
        self.assertEqual(cfg.execution.repeats, 5)
        self.assertFalse(cfg.visualization.auto_plot)

    def test_sub_config_setter(self):
        """Sub-config parameters can be set via assignment."""
        cfg = BenchRunCfg()
        cfg.cache.cache_results = True
        cfg.execution.repeats = 10
        self.assertTrue(cfg.cache.cache_results)
        self.assertEqual(cfg.execution.repeats, 10)

    def test_default_sub_config_init(self):
        """Default sub-configs created when not explicitly provided."""
        cfg = BenchRunCfg()
        cfg.cache.cache_results = True
        cfg.execution.repeats = 5
        self.assertTrue(cfg.cache.cache_results)
        self.assertEqual(cfg.execution.repeats, 5)

    def test_deep_copy(self):
        """deep() creates independent copy."""
        cfg = BenchRunCfg(execution=ExecutionCfg(repeats=5))
        cfg_copy = cfg.deep()
        cfg_copy.execution.repeats = 10
        self.assertEqual(cfg.execution.repeats, 5)
        self.assertEqual(cfg_copy.execution.repeats, 10)

    def test_deep_copy_sub_configs_not_shared(self):
        """deep() creates independent sub-config instances."""
        cfg = BenchRunCfg()
        cfg.cache.cache_results = False
        cfg_copy = cfg.deep()

        # Sub-config objects must not be shared
        self.assertIsNot(cfg.cache, cfg_copy.cache)
        self.assertIsNot(cfg.execution, cfg_copy.execution)
        self.assertIsNot(cfg.display, cfg_copy.display)
        self.assertIsNot(cfg.visualization, cfg_copy.visualization)
        self.assertIsNot(cfg.time, cfg_copy.time)

        # Mutating copy must not affect original
        cfg_copy.cache.cache_results = True
        self.assertTrue(cfg_copy.cache.cache_results)
        self.assertFalse(cfg.cache.cache_results)


class TestBenchCfgInheritance(unittest.TestCase):
    """Test BenchCfg inherits from BenchRunCfg."""

    def test_inherits_sub_config_access(self):
        """BenchCfg has sub-config parameter access."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            cache=CacheCfg(cache_results=True),
            execution=ExecutionCfg(repeats=3),
        )
        self.assertTrue(cfg.cache.cache_results)
        self.assertEqual(cfg.execution.repeats, 3)

    def test_over_time_works(self):
        """over_time parameter works correctly."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            time=TimeCfg(over_time=True),
        )
        self.assertTrue(cfg.time.over_time)

    def test_hash_persistent_varies_with_repeats(self):
        """hash_persistent changes when repeats differs."""
        cfg1 = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            execution=ExecutionCfg(repeats=1),
        )
        cfg2 = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            execution=ExecutionCfg(repeats=2),
        )
        # With include_repeats=True, hashes should differ
        self.assertNotEqual(cfg1.hash_persistent(True), cfg2.hash_persistent(True))
        # With include_repeats=False, hashes should be equal
        self.assertEqual(cfg1.hash_persistent(False), cfg2.hash_persistent(False))

    def test_describe_benchmark_includes_sub_config_fields(self):
        """describe_benchmark output includes sub-config values."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            meta_vars=[],
            bench_name="test",
            title="test",
            execution=ExecutionCfg(level=5),
            cache=CacheCfg(cache_results=True, cache_samples=True),
        )
        description = cfg.describe_benchmark()
        # Check sub-config fields appear in output
        self.assertIn("bench level: 5", description)
        self.assertIn("cache_results: True", description)
        self.assertIn("cache_samples True", description)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of imports."""

    def test_import_from_bench_cfg_module(self):
        """Classes importable from bencher.bench_cfg."""
        # pylint: disable=import-outside-toplevel,reimported
        from bencher.bench_cfg import DimsCfg as DimsCfgImport

        self.assertIsNotNone(BenchRunCfg)
        self.assertIsNotNone(BenchCfg)
        self.assertIsNotNone(DimsCfgImport)

    def test_import_from_bencher(self):
        """Classes importable from bencher."""
        # pylint: disable=import-outside-toplevel,reimported
        from bencher import BenchRunCfg as RunCfgImport, BenchCfg as CfgImport

        self.assertIsNotNone(RunCfgImport)
        self.assertIsNotNone(CfgImport)

    def test_import_new_sub_configs(self):
        """New sub-config classes are importable."""
        # pylint: disable=import-outside-toplevel,reimported
        from bencher.bench_cfg import (
            CacheCfg as CacheImport,
            ExecutionCfg as ExecImport,
            DisplayCfg as DispImport,
        )

        self.assertIsNotNone(CacheImport)
        self.assertIsNotNone(ExecImport)
        self.assertIsNotNone(DispImport)


if __name__ == "__main__":
    unittest.main()
