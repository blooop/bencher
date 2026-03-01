import unittest
import bencher as bch
from bencher.example.meta.example_meta import BenchableObject, FunctionVariant


class TestBenchMeta(unittest.TestCase):
    def test_repeats_equal(self):
        bench = bch.Bench("bench", BenchableObject())

        res1 = bench.plot_sweep(
            "repeats", input_vars=[BenchableObject.param.float1], run_cfg=bch.BenchRunCfg(repeats=1)
        )

        res1_eq = bench.plot_sweep(
            "repeats", input_vars=[BenchableObject.param.float1], run_cfg=bch.BenchRunCfg(repeats=1)
        )

        res2 = bench.plot_sweep(
            "repeats", input_vars=[BenchableObject.param.float1], run_cfg=bch.BenchRunCfg(repeats=2)
        )

        self.assertTrue(
            res1.to_dataset(bch.ReduceType.NONE).identical(res1_eq.to_dataset(bch.ReduceType.NONE)),
            "created with identical settings so should be equal",
        )

        self.assertFalse(
            res1.to_dataset(bch.ReduceType.NONE).identical(res2.to_dataset(bch.ReduceType.NONE)),
            "different number of repeats so should not be equal",
        )

        res1_ds = res1.to_dataset(bch.ReduceType.SQUEEZE)
        res2_ds = res2.to_dataset(bch.ReduceType.REDUCE)

        self.assertFalse(
            res1_ds.identical(res2_ds), "should not be equal because of std_dev column"
        )

        res2_ds = res2_ds.drop_vars("distance_std")
        res2_ds = res2_ds.drop_vars("sample_noise_std")

        print(res1_ds)
        print(res2_ds)
        print(res1_ds["distance"].attrs)
        print(res2_ds["distance"].attrs)

        self.assertTrue(
            res1_ds.equals(res2_ds), "should be equal because of removed std_dev column"
        )

        self.assertTrue(
            res1_ds.identical(res2_ds), "should be equal because of removed std_dev column"
        )

    def test_visual_distinction(self):
        """Verify different category combinations produce different output values."""
        obj = BenchableObject()

        for dims in range(4):
            obj.active_dims = dims
            values = set()
            for wave_val in [True, False]:
                for variant_val in FunctionVariant:
                    for transform_val in ["normal", "inverted"]:
                        obj.wave = wave_val
                        obj.variant = variant_val
                        obj.transform = transform_val
                        obj.float1 = 0.3
                        obj.float2 = 0.4
                        obj.float3 = 0.6
                        obj()
                        values.add(round(obj.distance, 6))
            # All 8 combinations (2 wave * 2 variant * 2 transform) should produce
            # at least 4 distinct values (inverted pairs share magnitude but differ in sign)
            self.assertGreaterEqual(
                len(values),
                4,
                f"Expected at least 4 distinct values for {dims}D, got {len(values)}: {values}",
            )
