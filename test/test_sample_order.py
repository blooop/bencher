import unittest
import bencher as bch


# Single-class format to ensure picklability and capture traversal order
class OrderExample(bch.ParametrizedSweep):
    # INPUTS
    a = bch.IntSweep(default=0, bounds=[0, 2])  # 3 samples
    b = bch.IntSweep(default=0, bounds=[0, 1])  # 2 samples

    # RESULTS
    call_index = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Maintain a per-instance counter to reflect traversal order
        idx = getattr(self, "_call_counter", 0)
        self.call_index = idx
        setattr(self, "_call_counter", idx + 1)

        return super().__call__()


class TestSampleOrder(unittest.TestCase):
    def test_sample_order_does_not_change_results_or_dims(self):
        # Use deterministic example worker (no noise by default)
        bench1 = bch.Bench("sample_order_eq_1", bch.ExampleBenchCfg())
        bench2 = bch.Bench("sample_order_eq_2", bch.ExampleBenchCfg())

        input_vars = [
            bch.ExampleBenchCfg.param.theta,
            bch.ExampleBenchCfg.param.postprocess_fn,
        ]
        result_vars = [bch.ExampleBenchCfg.param.out_sin]
        run_cfg = bch.BenchRunCfg(
            repeats=1,
            over_time=False,
            auto_plot=False,
            cache_results=False,
            cache_samples=False,
            executor=bch.Executors.SERIAL,
            level=2,  # keep dataset small and consistent without mutating class defaults
        )

        res_in = bench1.plot_sweep(
            title="inorder",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=run_cfg,
            sample_order=bch.SampleOrder.INORDER,
        )
        res_rev = bench2.plot_sweep(
            title="reversed",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=run_cfg,
            sample_order=bch.SampleOrder.REVERSED,
        )

        ds_in = res_in.to_xarray()
        ds_rev = res_rev.to_xarray()

        # Dataset values must be identical regardless of sampling order
        self.assertTrue(ds_in.equals(ds_rev))

        # Dimension order should match input_vars order and remain unchanged
        var_name = bch.ExampleBenchCfg.param.out_sin.name
        self.assertEqual(
            list(ds_in[var_name].dims)[:2],
            [v.name for v in input_vars],
        )
        self.assertEqual(list(ds_in[var_name].dims), list(ds_rev[var_name].dims))

    def test_sample_order_reverses_traversal_only(self):
        def run(sample_order: bch.SampleOrder):
            bench = bch.Bench("order_test", OrderExample())
            res = bench.plot_sweep(
                title="order",
                input_vars=[OrderExample.param.a, OrderExample.param.b],
                result_vars=[OrderExample.param.call_index],
                run_cfg=bch.BenchRunCfg(
                    repeats=1,
                    over_time=False,
                    auto_plot=False,
                    cache_results=False,
                    cache_samples=False,
                    executor=bch.Executors.SERIAL,
                ),
                sample_order=sample_order,
            )
            return res.to_xarray()[OrderExample.param.call_index.name].values.flatten().tolist()

        inorder = run(bch.SampleOrder.INORDER)
        reversed_order = run(bch.SampleOrder.REVERSED)

        # In-order should be 0..N-1
        self.assertEqual(inorder, list(range(len(inorder))))

        # For reversed traversal, the left-most input (a) varies fastest.
        # Compute expected flattened sequence using dims order (a,b).
        la = len(OrderExample.param.a.values())
        lb = len(OrderExample.param.b.values())
        expected_rev = [None] * (la * lb)
        for i in range(la):
            for j in range(lb):
                # Flatten index position for (i,j) in C-order is i*lb + j
                pos = i * lb + j
                # Sampling sequence index when 'a' varies fastest: j*la + i
                expected_rev[pos] = j * la + i

        self.assertEqual(reversed_order, expected_rev)


if __name__ == "__main__":
    unittest.main()
