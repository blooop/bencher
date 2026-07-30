"""Plan 16 — ``bn.sweep_identity`` must agree with a real run, byte for byte.

The whole value of a public identity API is that it cannot drift from the runtime,
so the central test here is equivalence against an actual ``plot_sweep``, over
every declaration form ``plot_sweep`` accepts. A test that only pinned
``sweep_identity`` against itself would pass forever while the hashing rule moved
underneath it -- which is exactly the failure mode of the downstream
transcriptions this API exists to replace.
"""

from __future__ import annotations

import json
import math
import pickle
import unittest
from dataclasses import asdict

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg


def _real_run(run_cfg: bn.BenchRunCfg | None = None, **kwargs) -> bn.SweepIdentity:
    """Actually run the sweep and report the identity it was stored under."""
    cfg = run_cfg if run_cfg is not None else bn.BenchRunCfg()
    cfg.auto_plot = False
    cfg.cache_results = False
    cfg.cache_samples = False
    bench = ExampleBenchCfg().to_bench(cfg)
    try:
        return bench.plot_sweep(plot_callbacks=False, **kwargs).identity
    finally:
        bench.close()


DECLARATIONS = {
    "param_object": dict(
        input_vars=[ExampleBenchCfg.param.theta],
        result_vars=[ExampleBenchCfg.param.out_sin],
    ),
    "by_name": dict(input_vars=["theta"], result_vars=["out_sin"]),
    "sweep_spec_bounds": dict(
        input_vars=[bn.sweep("theta", bounds=(0, 1), samples=3)],
        result_vars=["out_sin"],
    ),
    "sweep_spec_values": dict(
        input_vars=[bn.sweep("theta", [0.0, 0.5, 1.0])],
        result_vars=["out_sin"],
    ),
    "two_inputs": dict(
        input_vars=[bn.sweep("theta", samples=2), bn.sweep("offset", samples=2)],
        result_vars=["out_sin", "out_cos"],
    ),
    "consts_as_dict": dict(
        input_vars=[bn.sweep("theta", samples=2)],
        result_vars=["out_sin"],
        const_vars={"offset": 0.1},
    ),
    "consts_as_pairs": dict(
        input_vars=[bn.sweep("theta", samples=2)],
        result_vars=["out_sin"],
        const_vars=[(ExampleBenchCfg.param.offset, 0.1)],
    ),
    "tagged": dict(
        input_vars=[bn.sweep("theta", samples=2)],
        result_vars=["out_sin"],
        tag="nightly",
    ),
    "no_inputs": dict(input_vars=[], result_vars=["out_sin"], const_vars={"theta": 0.5}),
}

RUN_CFGS = {
    "default": dict(),
    "over_time": dict(over_time=True),
    "repeats_3": dict(repeats=3),
    "subsampling_2": dict(subsampling_divisions=2),
    "subsampling_4_over_time": dict(subsampling_divisions=4, over_time=True, repeats=2),
    "samples_per_var": dict(samples_per_var=4),
    "run_tag": dict(run_tag="rt"),
}


class TestEquivalence(unittest.TestCase):
    """sweep_identity(...) == the identity of an actual run of the same sweep."""

    def _check(self, decl: dict, run_kwargs: dict) -> None:
        predicted = bn.sweep_identity(
            worker=ExampleBenchCfg, run_cfg=bn.BenchRunCfg(**run_kwargs), **decl
        )
        actual = _real_run(bn.BenchRunCfg(**run_kwargs), **decl)
        self.assertEqual(predicted.cache_key, actual.cache_key, "cache_key")
        self.assertEqual(predicted.history_key, actual.history_key, "history_key")
        self.assertEqual(predicted.sample_key, actual.sample_key, "sample_key")
        self.assertEqual(predicted.bench_name, actual.bench_name)
        self.assertEqual(predicted.tag, actual.tag)
        self.assertEqual(predicted.repeats, actual.repeats)
        self.assertEqual(predicted.over_time, actual.over_time)
        self.assertEqual(predicted.summary, actual.summary)
        self.assertEqual(predicted, actual)

    def test_every_declaration_form_default_run(self) -> None:
        for name, decl in DECLARATIONS.items():
            with self.subTest(declaration=name):
                self._check(decl, {})

    def test_every_run_cfg_shape(self) -> None:
        decl = DECLARATIONS["sweep_spec_bounds"]
        for name, run_kwargs in RUN_CFGS.items():
            with self.subTest(run_cfg=name):
                self._check(decl, run_kwargs)

    def test_auto_discovered_vars(self) -> None:
        """input_vars=None auto-discovers; the prediction must discover the same."""
        self._check(dict(result_vars=["out_sin"], const_vars={}), dict(subsampling_divisions=2))


class TestKeySemantics(unittest.TestCase):
    def _ident(self, **kwargs) -> bn.SweepIdentity:
        return bn.sweep_identity(worker=ExampleBenchCfg, **kwargs)

    def test_history_key_ignores_result_vars_and_cache_key_does_not(self) -> None:
        """The plan 09/14 contract, asserted through the new surface."""
        one = self._ident(input_vars=["theta"], result_vars=["out_sin"])
        two = self._ident(input_vars=["theta"], result_vars=["out_sin", "out_cos"])
        self.assertEqual(one.history_key, two.history_key)
        self.assertNotEqual(one.cache_key, two.cache_key)

    def test_title_and_description_do_not_move_any_key(self) -> None:
        base = self._ident(input_vars=["theta"], result_vars=["out_sin"])
        titled = self._ident(
            input_vars=["theta"],
            result_vars=["out_sin"],
            title="Something else entirely",
            description="d",
            post_description="p",
        )
        self.assertEqual(base.cache_key, titled.cache_key)
        self.assertEqual(base.history_key, titled.history_key)

    def test_bench_name_moves_every_key(self) -> None:
        """The rename case: identical declaration, different name, different series."""
        a = self._ident(bench_name="Alpha", input_vars=["theta"], result_vars=["out_sin"])
        b = self._ident(bench_name="Beta", input_vars=["theta"], result_vars=["out_sin"])
        self.assertNotEqual(a.history_key, b.history_key)
        self.assertNotEqual(a.cache_key, b.cache_key)

    def test_bench_name_defaults_to_the_worker_class_name(self) -> None:
        """Matches create_bench, so a prediction and a to_bench() run agree."""
        ident = self._ident(input_vars=["theta"], result_vars=["out_sin"])
        self.assertEqual(ident.bench_name, "ExampleBenchCfg")

    def test_subsampling_divisions_moves_the_key(self) -> None:
        """Input vars are reshaped before hashing, so the run config is part of identity."""
        keys = {
            n: self._ident(
                input_vars=["theta"],
                result_vars=["out_sin"],
                run_cfg=bn.BenchRunCfg(subsampling_divisions=n),
            ).history_key
            for n in (0, 2, 4)
        }
        self.assertEqual(len(set(keys.values())), 3, keys)

    def test_run_tag_is_prefixed_to_tag(self) -> None:
        ident = self._ident(
            input_vars=["theta"],
            result_vars=["out_sin"],
            tag="b",
            run_cfg=bn.BenchRunCfg(run_tag="a_"),
        )
        self.assertEqual(ident.tag, "a_b")

    def test_input_var_order_matters_but_result_var_order_does_not(self) -> None:
        ab = self._ident(input_vars=["theta", "offset"], result_vars=["out_sin", "out_cos"])
        ba = self._ident(input_vars=["offset", "theta"], result_vars=["out_cos", "out_sin"])
        self.assertNotEqual(ab.history_key, ba.history_key)
        reordered_results = self._ident(
            input_vars=["theta", "offset"], result_vars=["out_cos", "out_sin"]
        )
        self.assertEqual(ab.cache_key, reordered_results.cache_key)


class TestValueSemantics(unittest.TestCase):
    def setUp(self) -> None:
        self.ident = bn.sweep_identity(
            worker=ExampleBenchCfg, input_vars=["theta"], result_vars=["out_sin"]
        )

    def test_frozen(self) -> None:
        with self.assertRaises(Exception):
            self.ident.cache_key = "x"

    def test_pickle_round_trip_is_unchanged(self) -> None:
        again = pickle.loads(pickle.dumps(self.ident))
        self.assertEqual(again, self.ident)
        self.assertEqual(again.cache_key, self.ident.cache_key)
        self.assertEqual(again.summary, self.ident.summary)

    def test_json_round_trip_needs_no_custom_encoder(self) -> None:
        blob = json.dumps(asdict(self.ident))
        back = json.loads(blob)
        self.assertEqual(back["cache_key"], self.ident.cache_key)
        self.assertEqual(back["history_key"], self.ident.history_key)

    def test_usable_as_a_dict_key(self) -> None:
        twin = bn.sweep_identity(
            worker=ExampleBenchCfg, input_vars=["theta"], result_vars=["out_sin"]
        )
        self.assertEqual({self.ident: 1, twin: 2}, {self.ident: 2})

    def test_summary_is_excluded_from_equality(self) -> None:
        """It is derived explanation, and a dict field would break hashing."""
        from dataclasses import fields

        (summary_field,) = [f for f in fields(bn.SweepIdentity) if f.name == "summary"]
        self.assertFalse(summary_field.compare)
        self.assertIsInstance(hash(self.ident), int)


class TestErrors(unittest.TestCase):
    def test_by_name_variable_without_a_worker_raises_the_existing_error(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            bn.sweep_identity(bench_name="X", input_vars=["theta"], result_vars=["out_sin"])
        self.assertIn("without a worker class instance", str(ctx.exception))

    def test_no_worker_and_no_bench_name_raises(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            bn.sweep_identity(input_vars=[], result_vars=[])
        self.assertIn("bench_name", str(ctx.exception))

    def test_unknown_variable_name_lists_available_parameters(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            bn.sweep_identity(worker=ExampleBenchCfg, input_vars=["nope"], result_vars=["out_sin"])
        self.assertIn("Available parameters", str(ctx.exception))


class TestExplain(unittest.TestCase):
    def setUp(self) -> None:
        self.ident = bn.sweep_identity(
            worker=ExampleBenchCfg,
            input_vars=["theta"],
            result_vars=["out_sin"],
            const_vars={"offset": 0.2},
            tag="nightly",
        )

    def test_names_title_as_excluded(self) -> None:
        """Regression guard for the exclusion documented in hash_persistent."""
        text = self.ident.explain()
        excluded = text.split("excluded on purpose")[1]
        self.assertIn("title", excluded)

    def test_reports_both_keys_and_the_contributing_fields(self) -> None:
        text = self.ident.explain()
        self.assertIn(self.ident.cache_key, text)
        self.assertIn(self.ident.history_key, text)
        for expected in ("bench_name", "tag", "repeats", "over_time", "input_vars"):
            self.assertIn(expected, text)

    def test_diff_identities_names_what_moved(self) -> None:
        other = bn.sweep_identity(
            worker=ExampleBenchCfg,
            input_vars=["theta", "offset"],
            result_vars=["out_sin"],
            tag="nightly",
        )
        lines = bn.diff_identities(self.ident, other)
        self.assertTrue(any("inputs changed" in line for line in lines), lines)

    def test_diff_identities_accepts_raw_summaries(self) -> None:
        """The stored last-seen index holds dicts, not SweepIdentity values."""
        lines = bn.diff_identities(self.ident.summary, self.ident.summary)
        self.assertEqual(lines, [])


class TestConfigAccessors(unittest.TestCase):
    def test_bench_cfg_identity_matches_the_result_identity(self) -> None:
        cfg = bn.BenchRunCfg(subsampling_divisions=2, repeats=2)
        cfg.auto_plot = False
        cfg.cache_results = False
        cfg.cache_samples = False
        bench = ExampleBenchCfg().to_bench(cfg)
        try:
            res = bench.plot_sweep(
                input_vars=["theta"], result_vars=["out_sin"], plot_callbacks=False
            )
            self.assertEqual(res.bench_cfg.identity(), res.identity)
            self.assertEqual(res.identity.repeats, 2)
        finally:
            bench.close()

    def test_identity_of_an_unrun_config_needs_the_run_cfg(self) -> None:
        """repeats/over_time reach BenchCfg only through run_sweep's merge."""
        run_cfg = bn.BenchRunCfg(repeats=5)
        ident = bn.sweep_identity(
            worker=ExampleBenchCfg,
            input_vars=["theta"],
            result_vars=["out_sin"],
            run_cfg=run_cfg,
        )
        self.assertEqual(ident.repeats, 5)


class TestNoRuntimeCost(unittest.TestCase):
    def test_the_worker_is_never_called(self) -> None:
        calls = []

        class Probe(bn.ParametrizedSweep):
            x = bn.FloatSweep(default=0, bounds=(0, 1), samples=3)
            y = bn.ResultFloat()

            def __call__(self, **kwargs):
                calls.append(kwargs)
                return {"y": 1.0}

        ident = bn.sweep_identity(worker=Probe, input_vars=["x"], result_vars=["y"])
        self.assertEqual(calls, [])
        self.assertTrue(ident.cache_key)

    def test_a_worker_class_is_never_instantiated(self) -> None:
        """The case that makes identity reachable for an expensive benchmark.

        A worker that needs live resources -- an attached robot, a running
        simulator, an open device -- cannot be constructed just to be asked what
        its parameters are, and requiring an instance would put identity out of
        reach of exactly the benchmarks whose runs are worth checking first.
        """

        class NeedsHardware(bn.ParametrizedSweep):
            x = bn.FloatSweep(default=0, bounds=(0, 1), samples=3)
            y = bn.ResultFloat()

            def __init__(self, **params):
                raise RuntimeError("requires an active sampling context")

        ident = bn.sweep_identity(worker=NeedsHardware, input_vars=["x"], result_vars=["y"])
        self.assertTrue(ident.history_key)
        self.assertEqual(ident.bench_name, "NeedsHardware")

    def test_a_class_and_an_instance_agree(self) -> None:
        by_class = bn.sweep_identity(
            worker=ExampleBenchCfg, input_vars=["theta"], result_vars=["out_sin"]
        )
        by_instance = bn.sweep_identity(
            worker=ExampleBenchCfg(), input_vars=["theta"], result_vars=["out_sin"]
        )
        self.assertEqual(by_class, by_instance)

    def test_auto_discovery_works_from_a_class(self) -> None:
        """get_inputs_only / get_input_defaults / get_results_only are classmethods."""
        by_class = bn.sweep_identity(worker=ExampleBenchCfg)
        by_instance = bn.sweep_identity(worker=ExampleBenchCfg())
        self.assertEqual(by_class, by_instance)
        self.assertTrue(by_class.summary["inputs"])
        self.assertTrue(by_class.summary["results"])

    def test_a_zero_length_declaration_still_produces_keys(self) -> None:
        ident = bn.sweep_identity(
            worker=ExampleBenchCfg, input_vars=[], result_vars=["out_sin"], const_vars={}
        )
        self.assertTrue(ident.cache_key)
        self.assertNotEqual(ident.cache_key, ident.history_key)


class TestMathImportedForRealism(unittest.TestCase):
    """theta's bounds are [0, pi]; a values= declaration inside them is realistic."""

    def test_explicit_values_within_bounds(self) -> None:
        ident = bn.sweep_identity(
            worker=ExampleBenchCfg,
            input_vars=[bn.sweep("theta", [0.0, math.pi / 2, math.pi])],
            result_vars=["out_sin"],
        )
        self.assertTrue(ident.history_key)


if __name__ == "__main__":
    unittest.main()
