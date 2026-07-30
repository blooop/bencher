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
from dataclasses import FrozenInstanceError, asdict
from unittest import mock

import bencher as bn
from bencher.bench_cfg import BenchCfg
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
    "param_object": {
        "input_vars": [ExampleBenchCfg.param.theta],
        "result_vars": [ExampleBenchCfg.param.out_sin],
    },
    "by_name": {"input_vars": ["theta"], "result_vars": ["out_sin"]},
    "sweep_spec_bounds": {
        "input_vars": [bn.sweep("theta", bounds=(0, 1), samples=3)],
        "result_vars": ["out_sin"],
    },
    "sweep_spec_values": {
        "input_vars": [bn.sweep("theta", [0.0, 0.5, 1.0])],
        "result_vars": ["out_sin"],
    },
    "two_inputs": {
        "input_vars": [bn.sweep("theta", samples=2), bn.sweep("offset", samples=2)],
        "result_vars": ["out_sin", "out_cos"],
    },
    "consts_as_dict": {
        "input_vars": [bn.sweep("theta", samples=2)],
        "result_vars": ["out_sin"],
        "const_vars": {"offset": 0.1},
    },
    "consts_as_pairs": {
        "input_vars": [bn.sweep("theta", samples=2)],
        "result_vars": ["out_sin"],
        "const_vars": [(ExampleBenchCfg.param.offset, 0.1)],
    },
    "tagged": {
        "input_vars": [bn.sweep("theta", samples=2)],
        "result_vars": ["out_sin"],
        "tag": "nightly",
    },
    "no_inputs": {"input_vars": [], "result_vars": ["out_sin"], "const_vars": {"theta": 0.5}},
}

RUN_CFGS = {
    "default": {},
    "over_time": {"over_time": True},
    "repeats_3": {"repeats": 3},
    "subsampling_2": {"subsampling_divisions": 2},
    "subsampling_4_over_time": {"subsampling_divisions": 4, "over_time": True, "repeats": 2},
    "samples_per_var": {"samples_per_var": 4},
    "run_tag": {"run_tag": "rt"},
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
        self._check({"result_vars": ["out_sin"], "const_vars": {}}, {"subsampling_divisions": 2})


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

    def test_explicit_repeats_and_over_time_win_over_the_run_cfg(self) -> None:
        """The keyword overrides are documented as overrides, so pin the precedence."""
        run_cfg = bn.BenchRunCfg(repeats=1, over_time=False)
        overridden = self._ident(
            input_vars=["theta"],
            result_vars=["out_sin"],
            run_cfg=run_cfg,
            repeats=3,
            over_time=True,
        )
        self.assertEqual(overridden.repeats, 3)
        self.assertTrue(overridden.over_time)
        # ...and the override reaches the keys, not just the reported fields.
        from_run_cfg = self._ident(input_vars=["theta"], result_vars=["out_sin"], run_cfg=run_cfg)
        self.assertNotEqual(overridden.history_key, from_run_cfg.history_key)
        self.assertEqual(
            overridden.history_key,
            self._ident(
                input_vars=["theta"],
                result_vars=["out_sin"],
                run_cfg=bn.BenchRunCfg(repeats=3, over_time=True),
            ).history_key,
        )

    def test_the_run_cfg_passed_in_is_not_mutated_by_the_overrides(self) -> None:
        run_cfg = bn.BenchRunCfg(repeats=1, over_time=False)
        self._ident(
            input_vars=["theta"],
            result_vars=["out_sin"],
            run_cfg=run_cfg,
            repeats=9,
            over_time=True,
        )
        self.assertEqual(run_cfg.repeats, 1)
        self.assertFalse(run_cfg.over_time)
        self.assertFalse(run_cfg.dry_run)

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
        with self.assertRaises(FrozenInstanceError):
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

    def test_asking_for_an_identity_does_not_reconfigure_the_config(self) -> None:
        """BenchCfg subclasses BenchRunCfg, so an in-place merge would rewrite every
        run-side field (repeats, cache_results, dry_run, ...) of a config the caller
        still holds -- turning a query into a silent reconfiguration of the next run."""
        cfg = bn.BenchRunCfg()
        cfg.auto_plot = False
        cfg.dry_run = True
        bench = ExampleBenchCfg().to_bench(cfg)
        try:
            res = bench.plot_sweep(
                input_vars=["theta"], result_vars=["out_sin"], plot_callbacks=False
            )
            merged = [k for k in bn.BenchRunCfg.param if k in res.bench_cfg.param]
            before = {k: getattr(res.bench_cfg, k) for k in merged}
            ident = res.bench_cfg.identity(
                bn.BenchRunCfg(repeats=7, over_time=True, cache_results=True)
            )
            self.assertEqual(ident.repeats, 7)
            self.assertTrue(ident.over_time)
            self.assertEqual(before, {k: getattr(res.bench_cfg, k) for k in merged})
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


def _dry_identity(run_cfg: bn.BenchRunCfg | None = None, **plot_sweep_kwargs) -> bn.SweepIdentity:
    """Identity of a declaration made through a real ``plot_sweep``, without sampling.

    Reaches the ``plot_sweep`` keywords ``sweep_identity`` deliberately does not
    expose -- ``aggregate``, ``agg_fn``, ``plot_callbacks`` -- which land on
    ``BenchCfg`` and so are the ones worth proving *inert*.
    """
    cfg = bn.BenchRunCfg() if run_cfg is None else run_cfg.deep()
    cfg.dry_run = True
    cfg.auto_plot = False
    bench = ExampleBenchCfg().to_bench(cfg)
    try:
        return bn.identity_of(bench.plot_sweep(run_cfg=cfg, **plot_sweep_kwargs).bench_cfg, cfg)
    finally:
        bench.close()


_GUARD_BASE = {
    "input_vars": ["theta"],
    "result_vars": ["out_sin"],
    "const_vars": {"offset": 0.1},
}


class TestDocumentedFieldsMatchTheHashingRule(unittest.TestCase):
    """``IDENTITY_FIELDS`` / ``EXCLUDED_FIELDS`` are prose about code that lives elsewhere.

    ``explain()`` is only worth reading if those two lists are true of
    ``BenchCfg.hash_persistent``, and a hand-kept description of a hashing rule
    defined somewhere else is exactly the transcription this API exists to delete --
    so each entry is checked behaviourally, by changing that field and asserting a key
    does or does not move. The coverage map is asserted to name every entry, so
    extending either list without a matching check fails here rather than silently
    documenting something untrue.
    """

    def _ident(self, **kwargs) -> bn.SweepIdentity:
        return bn.sweep_identity(worker=ExampleBenchCfg, **{**_GUARD_BASE, **kwargs})

    def _assert_keys_move(self, a: bn.SweepIdentity, b: bn.SweepIdentity) -> None:
        self.assertNotEqual(a.cache_key, b.cache_key, "cache_key")
        self.assertNotEqual(a.history_key, b.history_key, "history_key")

    def _assert_no_key_moves(self, a: bn.SweepIdentity, b: bn.SweepIdentity) -> None:
        self.assertEqual(a.cache_key, b.cache_key, "cache_key")
        self.assertEqual(a.history_key, b.history_key, "history_key")
        self.assertEqual(a.sample_key, b.sample_key, "sample_key")

    # --- contributing fields -------------------------------------------------

    def check_cache_version(self) -> None:
        """A version bump is meant to invalidate every key at once."""
        base = self._ident()
        with mock.patch("bencher.bench_cfg.CACHE_VERSION", 10_000):
            bumped = self._ident()
        self._assert_keys_move(base, bumped)
        self.assertNotEqual(base.sample_key, bumped.sample_key)

    def check_bench_name(self) -> None:
        self._assert_keys_move(self._ident(), self._ident(bench_name="Renamed"))

    def check_over_time(self) -> None:
        self._assert_keys_move(self._ident(), self._ident(over_time=True))

    def check_repeats(self) -> None:
        base, more = self._ident(), self._ident(repeats=3)
        self._assert_keys_move(base, more)
        # ...but not the sample key, which is hashed with include_repeats=False so a
        # single sample stays reusable across repeat counts.
        self.assertEqual(base.sample_key, more.sample_key)

    def check_tag(self) -> None:
        self._assert_keys_move(self._ident(), self._ident(tag="nightly"))

    def check_input_vars(self) -> None:
        """In list order: the order fixes the dimension layout of the result arrays."""
        two = {"input_vars": ["theta", "offset"], "const_vars": {}}
        self._assert_keys_move(
            self._ident(**two), self._ident(input_vars=["offset", "theta"], const_vars={})
        )
        self._assert_keys_move(self._ident(**two), self._ident(input_vars=["theta"], const_vars={}))

    def check_result_vars(self) -> None:
        """An unordered set, and in the cache key only."""
        one = self._ident()
        two = self._ident(result_vars=["out_sin", "out_cos"])
        self.assertNotEqual(one.cache_key, two.cache_key)
        self.assertEqual(one.history_key, two.history_key)
        self.assertEqual(two.cache_key, self._ident(result_vars=["out_cos", "out_sin"]).cache_key)

    def check_const_vars(self) -> None:
        """An unordered set: const order only reaches the title string."""
        self._assert_keys_move(self._ident(), self._ident(const_vars={"offset": 0.2}))
        pair = [(ExampleBenchCfg.param.offset, 0.1), (ExampleBenchCfg.param.noisy, True)]
        self.assertEqual(
            self._ident(const_vars=pair).cache_key,
            self._ident(const_vars=list(reversed(pair))).cache_key,
        )

    # --- fields excluded on purpose ------------------------------------------

    def check_title(self) -> None:
        self._assert_no_key_moves(self._ident(), self._ident(title="Something else entirely"))

    def check_descriptions(self) -> None:
        self._assert_no_key_moves(self._ident(), self._ident(description="d", post_description="p"))

    def check_aggregation(self) -> None:
        """``agg_over_dims``/``agg_fn`` land on BenchCfg, and must stay inert there."""
        self._assert_no_key_moves(
            _dry_identity(input_vars=["theta", "offset"], result_vars=["out_sin"]),
            _dry_identity(
                input_vars=["theta", "offset"],
                result_vars=["out_sin"],
                aggregate=True,
                agg_fn="max",
            ),
        )

    def check_sample_order(self) -> None:
        """Sampling traversal only -- it never reaches BenchCfg at all."""
        self.assertNotIn("sample_order", BenchCfg.param)
        decl = {"input_vars": [bn.sweep("theta", samples=2)], "result_vars": ["out_sin"]}
        self._assert_no_key_moves(
            _real_run(**decl, sample_order=bn.SampleOrder.INORDER),
            _real_run(**decl, sample_order=bn.SampleOrder.REVERSED),
        )

    def check_plotting(self) -> None:
        """``plot_callbacks`` is stored on BenchCfg; ``auto_plot`` is merged onto it."""
        decl = {"input_vars": ["theta"], "result_vars": ["out_sin"]}
        self._assert_no_key_moves(
            _dry_identity(**decl, plot_callbacks=False),
            _dry_identity(**decl, plot_callbacks=True),
        )
        self._assert_no_key_moves(
            _dry_identity(**decl, plot_callbacks=False),
            _dry_identity(bn.BenchRunCfg(auto_plot=True), **decl, plot_callbacks=False),
        )

    def _checks(self) -> dict:
        return {
            "CACHE_VERSION": self.check_cache_version,
            "bench_name": self.check_bench_name,
            "over_time": self.check_over_time,
            "repeats": self.check_repeats,
            "tag": self.check_tag,
            "input_vars (in list order)": self.check_input_vars,
            "result_vars (as an unordered set; cache_key only)": self.check_result_vars,
            "const_vars (as an unordered set)": self.check_const_vars,
            "title": self.check_title,
            "description / post_description": self.check_descriptions,
            "aggregate / agg_fn": self.check_aggregation,
            "sample_order": self.check_sample_order,
            "plot_callbacks / auto_plot": self.check_plotting,
        }

    def test_every_documented_field_has_a_check(self) -> None:
        """Adding a field to either list without a check fails here."""
        self.assertEqual(set(self._checks()), set(bn.IDENTITY_FIELDS) | set(bn.EXCLUDED_FIELDS))

    def test_each_documented_field_behaves_as_documented(self) -> None:
        for field_name, check in self._checks().items():
            with self.subTest(field=field_name):
                check()


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
