"""Plan 20 — a variable declared twice must never quietly change identity.

The result-variable case is the one that mattered: ``result_vars=["y", "y"]``
produced a dataset byte-identical to ``result_vars=["y"]`` under a *different*
cache and history key, so a benchmark ran, reported correct numbers, and appended
to a trend line other than the one it appeared to belong to. Nothing said so.
"""

from __future__ import annotations

import unittest
import warnings

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg


def _bench() -> bn.Bench:
    cfg = bn.BenchRunCfg()
    cfg.visualization.auto_plot = False
    cfg.cache.results = False
    cfg.cache.samples = False
    return ExampleBenchCfg().to_bench(cfg)


def _sweep(**kwargs):
    bench = _bench()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res = bench.plot_sweep(plot_callbacks=False, **kwargs)
        return res, [str(w.message) for w in caught if w.category is UserWarning]
    finally:
        bench.close()


def _sweep_raw_warnings(**kwargs):
    """As ``_sweep``, but keeping the warning objects so attribution can be checked."""
    bench = _bench()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            bench.plot_sweep(plot_callbacks=False, **kwargs)
        return [w for w in caught if w.category is UserWarning]
    finally:
        bench.close()


class TestDuplicateResultVars(unittest.TestCase):
    """P2 — the silent series split, and its repair."""

    def test_duplicate_declaration_now_hashes_as_the_single_declaration(self) -> None:
        once, _ = _sweep(input_vars=["theta"], result_vars=["out_sin"])
        twice, warns = _sweep(input_vars=["theta"], result_vars=["out_sin", "out_sin"])

        self.assertEqual(
            once.bench_cfg.hash_persistent(True),
            twice.bench_cfg.hash_persistent(True),
            "a duplicated result var must not move the cache key",
        )
        self.assertEqual(
            once.bench_cfg.hash_persistent(True, include_result_vars=False),
            twice.bench_cfg.hash_persistent(True, include_result_vars=False),
        )
        self.assertTrue(any("declared twice" in w for w in warns), warns)

    def test_the_dataset_never_differed(self) -> None:
        once, _ = _sweep(input_vars=["theta"], result_vars=["out_sin"])
        twice, _ = _sweep(input_vars=["theta"], result_vars=["out_sin", "out_sin"])
        self.assertEqual(set(once.ds.data_vars), set(twice.ds.data_vars))
        self.assertEqual(dict(once.ds.sizes), dict(twice.ds.sizes))

    def test_config_holds_one_entry_per_name(self) -> None:
        res, _ = _sweep(input_vars=["theta"], result_vars=["out_sin", "out_cos", "out_sin"])
        names = [v.name for v in res.bench_cfg.result_vars]
        self.assertEqual(names, ["out_sin", "out_cos"])

    def test_the_warning_names_the_variable_and_both_positions(self) -> None:
        _res, warns = _sweep(
            input_vars=["theta"], result_vars=["out_sin", "out_cos", "out_bool", "out_cos"]
        )
        (msg,) = [w for w in warns if "declared twice" in w]
        self.assertIn("'out_cos'", msg)
        self.assertIn("positions 1 and 3", msg)

    def test_the_warning_is_attributed_to_the_caller_not_to_bencher(self) -> None:
        """Pins ``stacklevel``: the blame belongs to whoever wrote the declaration.

        The validator is several frames below ``plot_sweep``, so any refactor that
        adds or removes one has to move ``stacklevel`` with it or the warning
        starts pointing inside bencher, where the user can do nothing about it.
        """
        caught = _sweep_raw_warnings(input_vars=["theta"], result_vars=["out_sin", "out_sin"])
        (dup,) = [w for w in caught if "declared twice" in str(w.message)]
        self.assertEqual(
            dup.filename,
            __file__,
            f"warning blamed {dup.filename}:{dup.lineno}, not the calling test module",
        )

    def test_object_and_string_forms_are_compared_by_name(self) -> None:
        res, warns = _sweep(
            input_vars=["theta"],
            result_vars=["out_sin", ExampleBenchCfg.param.out_sin],
        )
        self.assertEqual([v.name for v in res.bench_cfg.result_vars], ["out_sin"])
        self.assertTrue(any("declared twice" in w for w in warns))

    def test_distinct_variables_are_never_judged_duplicates(self) -> None:
        res, warns = _sweep(input_vars=["theta"], result_vars=["out_sin", "out_cos", "out_bool"])
        self.assertEqual(len(res.bench_cfg.result_vars), 3)
        self.assertEqual([w for w in warns if "declared twice" in w], [])


class TestDuplicateInputVars(unittest.TestCase):
    """P4 — the xarray broadcasting error, replaced by a message about the cause."""

    def test_duplicate_input_raises_naming_the_variable_and_positions(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _sweep(input_vars=["theta", "theta"], result_vars=["out_sin"])
        msg = str(ctx.exception)
        self.assertIn("'theta'", msg)
        self.assertIn("positions [0, 1]", msg)
        self.assertIn("one dataset dimension", msg)

    def test_it_raises_before_any_sample_runs(self) -> None:
        """The xarray error arrived after the whole sweep had been executed."""
        calls = []

        class Probe(bn.ParametrizedSweep):
            x = bn.FloatSweep(default=0, bounds=(0, 1), samples=3)
            y = bn.ResultFloat()

            def __call__(self, **kwargs):
                calls.append(kwargs)
                return {"y": 1.0}

        cfg = bn.BenchRunCfg()
        cfg.visualization.auto_plot = False
        cfg.cache.results = False
        cfg.cache.samples = False
        bench = Probe().to_bench(cfg)
        try:
            with self.assertRaises(ValueError):
                bench.plot_sweep(input_vars=["x", "x"], result_vars=["y"], plot_callbacks=False)
        finally:
            bench.close()
        self.assertEqual(calls, [], "samples ran before the declaration was rejected")

    def test_mixed_declaration_forms_are_caught(self) -> None:
        for label, decl in {
            "str+object": ["theta", ExampleBenchCfg.param.theta],
            "str+spec": ["theta", bn.sweep("theta", samples=2)],
            "object+spec": [ExampleBenchCfg.param.theta, bn.sweep("theta", samples=2)],
        }.items():
            with self.subTest(forms=label), self.assertRaises(ValueError):
                _sweep(input_vars=decl, result_vars=["out_sin"])

    def test_three_occurrences_are_all_reported(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _sweep(input_vars=["theta", "theta", "theta"], result_vars=["out_sin"])
        self.assertIn("3 times", str(ctx.exception))
        self.assertIn("[0, 1, 2]", str(ctx.exception))

    def test_distinct_inputs_are_unaffected(self) -> None:
        res, _ = _sweep(
            input_vars=[bn.sweep("theta", samples=2), bn.sweep("offset", samples=2)],
            result_vars=["out_sin"],
        )
        self.assertEqual([v.name for v in res.bench_cfg.input_vars], ["theta", "offset"])


class TestDuplicateConstVars(unittest.TestCase):
    """P5 — the two accepted spellings behave the same way now."""

    def test_equal_values_are_deduped_silently(self) -> None:
        res, warns = _sweep(
            input_vars=["theta"],
            result_vars=["out_sin"],
            const_vars=[("offset", 0.1), ("offset", 0.1)],
        )
        names = [c[0].name for c in res.bench_cfg.const_vars]
        self.assertEqual(names.count("offset"), 1)
        self.assertEqual(warns, [])

    def test_conflicting_values_raise_naming_both(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _sweep(
                input_vars=["theta"],
                result_vars=["out_sin"],
                const_vars=[("offset", 0.1), ("offset", 0.2)],
            )
        msg = str(ctx.exception)
        self.assertIn("'offset'", msg)
        self.assertIn("0.1", msg)
        self.assertIn("0.2", msg)

    def test_dict_and_pair_forms_produce_identical_hashes(self) -> None:
        as_dict, _ = _sweep(
            input_vars=["theta"], result_vars=["out_sin"], const_vars={"offset": 0.1}
        )
        as_pairs, _ = _sweep(
            input_vars=["theta"], result_vars=["out_sin"], const_vars=[("offset", 0.1)]
        )
        self.assertEqual(
            as_dict.bench_cfg.hash_persistent(True), as_pairs.bench_cfg.hash_persistent(True)
        )

    def test_a_deduped_duplicate_hashes_as_the_single_declaration(self) -> None:
        once, _ = _sweep(input_vars=["theta"], result_vars=["out_sin"], const_vars={"offset": 0.1})
        twice, _ = _sweep(
            input_vars=["theta"],
            result_vars=["out_sin"],
            const_vars=[("offset", 0.1), ("offset", 0.1)],
        )
        self.assertEqual(
            once.bench_cfg.hash_persistent(True), twice.bench_cfg.hash_persistent(True)
        )


class TestHelperInIsolation(unittest.TestCase):
    """The helper is the one validation site, so plan 18's bind() can call it too."""

    def test_returns_the_lists_unchanged_when_there_are_no_duplicates(self) -> None:
        from bencher.sweep_executor import validate_declared_vars

        inputs = [ExampleBenchCfg.param.theta]
        results = [ExampleBenchCfg.param.out_sin]
        consts = [[ExampleBenchCfg.param.offset, 0.1]]
        out = validate_declared_vars(inputs, results, consts)
        self.assertEqual(out, (inputs, results, consts))

    def test_const_equality_uses_the_same_digest_the_hash_uses(self) -> None:
        """Values that hash the same are the same const for identity purposes."""
        from bencher.sweep_executor import validate_declared_vars

        _i, _r, consts = validate_declared_vars(
            [],
            [],
            [[ExampleBenchCfg.param.offset, 0.1], [ExampleBenchCfg.param.offset, 0.1]],
        )
        self.assertEqual(len(consts), 1)


class TestHashFoldsVariablesAsSets(unittest.TestCase):
    """The identity half of the fix, independent of the declaration-site validation.

    ``validate_declared_vars`` only guards ``plot_sweep``. ``hash_persistent``'s
    docstring has always promised result and const vars contribute as an *unordered
    set*, but a sorted tuple gave the ordering half of that and not the uniqueness
    half -- so any path that reaches a ``BenchCfg`` without passing the validator
    (built directly, or deserialized) could still hash a duplicate to a different
    key. These pin the promise at the place it is made.
    """

    @staticmethod
    def _cfg(result_vars: list, const_vars: list) -> bn.BenchCfg:
        return bn.BenchCfg(
            bench_name="dupes",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=result_vars,
            const_vars=const_vars,
        )

    def test_a_duplicate_result_var_does_not_move_the_key(self) -> None:
        once = self._cfg([ExampleBenchCfg.param.out_sin], [])
        twice = self._cfg([ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_sin], [])
        self.assertEqual(once.hash_persistent(True), twice.hash_persistent(True))

    def test_a_duplicate_const_does_not_move_the_key(self) -> None:
        pair = [ExampleBenchCfg.param.offset, 0.1]
        once = self._cfg([ExampleBenchCfg.param.out_sin], [pair])
        twice = self._cfg([ExampleBenchCfg.param.out_sin], [pair, list(pair)])
        self.assertEqual(once.hash_persistent(True), twice.hash_persistent(True))

    def test_distinct_vars_still_produce_distinct_keys(self) -> None:
        """Deduping must collapse repeats, not collapse the set itself."""
        one = self._cfg([ExampleBenchCfg.param.out_sin], [])
        two = self._cfg([ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_cos], [])
        self.assertNotEqual(one.hash_persistent(True), two.hash_persistent(True))

    def test_declaration_order_is_still_irrelevant(self) -> None:
        forward = self._cfg([ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_cos], [])
        reverse = self._cfg([ExampleBenchCfg.param.out_cos, ExampleBenchCfg.param.out_sin], [])
        self.assertEqual(forward.hash_persistent(True), reverse.hash_persistent(True))


if __name__ == "__main__":
    unittest.main()
