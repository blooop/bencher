"""The statistical evidence layer: evidence_stats against known values, infographic smoke
tests in both themes, and the evidence_report Markdown (docs/statistical_evidence.md)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

import bencher as bn
from bencher import evidence_report, evidence_stats as es, infographic as ig
from bencher.evidence_report import (
    analyse_data,
    data_from_rows,
    picture,
    report_from_results,
    report_from_rows,
)
from bencher.evidence_stats import VerdictKind

try:
    import scipy.stats as st
except ImportError:  # pragma: no cover - the pixi env has scipy
    st = None

needs_scipy = pytest.mark.skipif(st is None, reason="needs scipy")


# --------------------------------------------------------------------------------------
# Distributions and intervals.


@needs_scipy
@pytest.mark.parametrize("p", [1e-8, 0.01, 0.025, 0.3, 0.5, 0.9, 0.975, 0.999999])
def test_norm_ppf_matches_scipy(p):
    assert es.norm_ppf(p) == pytest.approx(st.norm.ppf(p), abs=1e-9)


@needs_scipy
@pytest.mark.parametrize(("p", "df"), [(0.95, 1), (0.95, 2.5), (0.975, 4.3), (0.05, 9), (0.9, 60)])
def test_t_quantile_and_cdf_match_scipy(p, df):
    assert es.t_ppf(p, df) == pytest.approx(st.t.ppf(p, df), abs=1e-9)
    assert es.t_cdf(-1.7, df) == pytest.approx(st.t.cdf(-1.7, df), abs=1e-12)


def test_wilson_hand_values():
    # 0/n upper bounds that Newcombe (1998) Table II's 0-event cases rest on.
    assert es.wilson(0, 10).high == pytest.approx(0.2775, abs=1e-4)
    assert es.wilson(0, 20).high == pytest.approx(0.1611, abs=1e-4)
    assert es.wilson(0, 10).low == 0.0
    ci = es.wilson(81, 263)  # Newcombe 1998 (single-proportion paper) example: 0.2553-0.3662
    assert (ci.low, ci.high) == pytest.approx((0.2553, 0.3662), abs=1e-4)


@pytest.mark.parametrize(
    ("k1", "n1", "k2", "n2", "low", "high"),
    [
        # Newcombe (1998), Stat Med 17:873, Table II, method 10 (hybrid score).
        (56, 70, 48, 80, 0.0524, 0.3339),
        (9, 10, 3, 10, 0.1705, 0.8090),
        (5, 56, 0, 29, -0.0381, 0.1926),
        (0, 10, 0, 20, -0.1611, 0.2775),
    ],
)
def test_newcombe_matches_published_table(k1, n1, k2, n2, low, high):
    ci = es.newcombe(k1, n1, k2, n2)
    assert (ci.low, ci.high) == pytest.approx((low, high), abs=1e-4)


def test_rule_of_three_and_exact_zero_bound():
    assert es.rule_of_three(30) == pytest.approx(0.1)
    assert es.zero_event_upper(30) == pytest.approx(1 - 0.05 ** (1 / 30))
    assert es.clopper_pearson_upper(0, 30) == pytest.approx(es.zero_event_upper(30))


@pytest.mark.parametrize(("p0", "runs"), [(0.05, 59), (0.10, 29), (0.01, 299)])
def test_runs_for_flake(p0, runs):
    assert es.runs_for_flake(p0) == runs


@needs_scipy
def test_clopper_pearson_matches_beta_quantile():
    assert es.clopper_pearson_upper(2, 30) == pytest.approx(st.beta.ppf(0.95, 3, 28), abs=1e-9)


@needs_scipy
def test_fisher_matches_scipy():
    for table in [(3, 18, 0, 18), (17, 18, 18, 18), (7, 12, 2, 11)]:
        k1, n1, k2, n2 = table
        expected = st.fisher_exact([[k1, k2], [n1 - k1, n2 - k2]]).pvalue
        assert es.fisher_exact_p(*table) == pytest.approx(expected, rel=1e-9)


@needs_scipy
def test_mcnemar_exact_is_binomial():
    assert es.mcnemar_exact_p(1, 7) == pytest.approx(st.binomtest(1, 8, 0.5).pvalue)


def test_quantile_ci_median_of_100():
    q = es.quantile_ci(np.arange(1, 101), 0.5)
    # The classic order-statistic CI for the median of n=100: x_(40)..x_(61).
    assert (q.low, q.high) == (40.0, 61.0)
    assert q.coverage >= 0.95


def test_quantile_ci_open_end_when_n_small():
    q = es.quantile_ci([1.0, 2.0, 3.0, 4.0, 5.0], 0.95)
    assert q.high is None


# --------------------------------------------------------------------------------------
# Multiplicity.


P = [0.01, 0.04, 0.03, 0.2, 0.005]


def test_holm_hand_values():
    assert es.holm(P) == pytest.approx([0.04, 0.09, 0.09, 0.2, 0.025])


@needs_scipy
def test_bh_matches_scipy():
    assert es.benjamini_hochberg(P) == pytest.approx(st.false_discovery_control(P))


def test_bh_hand_values():
    assert es.benjamini_hochberg(P) == pytest.approx([0.025, 0.05, 0.05, 0.2, 0.025])


# --------------------------------------------------------------------------------------
# Continuous effects.


def _lognormal_arms(n_base=15, n_cand=12, effect=-0.1, seed=1):
    rng = np.random.default_rng(seed)
    return rng.lognormal(0, 0.2, n_base), rng.lognormal(effect, 0.2, n_cand)


@needs_scipy
def test_bca_interval_matches_scipy_on_the_same_replicates():
    b, c = _lognormal_arms()
    lb, lc = np.log(b), np.log(c)
    res = st.bootstrap(
        (lc, lb),
        lambda x, y, axis: x.mean(axis) - y.mean(axis),
        confidence_level=0.9,
        n_resamples=10_000,
        method="BCa",
        rng=np.random.default_rng(0),
    )
    theta = lc.mean() - lb.mean()
    jacks = [
        np.array([np.delete(lc, i).mean() - lb.mean() for i in range(len(lc))]),
        np.array([lc.mean() - np.delete(lb, i).mean() for i in range(len(lb))]),
    ]
    ci = es._bca_interval(res.bootstrap_distribution, theta, jacks, 0.9)
    assert ci.low == pytest.approx(res.confidence_interval.low, abs=1e-9)
    assert ci.high == pytest.approx(res.confidence_interval.high, abs=1e-9)


@needs_scipy
def test_bca_effect_close_to_scipy():
    b, c = _lognormal_arms()
    e = es.continuous_effect(b, c)
    res = st.bootstrap(
        (np.log(c), np.log(b)),
        lambda x, y, axis: x.mean(axis) - y.mean(axis),
        confidence_level=0.9,
        method="BCa",
        rng=np.random.default_rng(0),
    )
    assert e.method.startswith("BCa")
    assert e.ci.low == pytest.approx(res.confidence_interval.low, abs=0.01)
    assert e.ci.high == pytest.approx(res.confidence_interval.high, abs=0.01)


@needs_scipy
def test_small_n_uses_welch_t_on_logs():
    b, c = _lognormal_arms(6, 5)
    e = es.continuous_effect(b, c)
    ref = st.ttest_ind(np.log(c), np.log(b), equal_var=False).confidence_interval(0.9)
    assert e.method == "Welch t on log values"
    assert (e.ci.low, e.ci.high) == pytest.approx((ref.low, ref.high), abs=1e-9)
    assert e.bootstrap is None


def test_paired_effect_cancels_shared_noise():
    rng = np.random.default_rng(3)
    machine = rng.normal(0, 0.4, 20)
    b = np.exp(machine + rng.normal(0, 0.02, 20))
    c = np.exp(machine - 0.1 + rng.normal(0, 0.02, 20))
    paired = es.continuous_effect(b, c, paired=True)
    unpaired = es.continuous_effect(b, c)
    width = paired.ci.high - paired.ci.low
    assert width * 5 < unpaired.ci.high - unpaired.ci.low
    assert paired.ci.high < 0
    assert "paired" in paired.method
    assert paired.robust is not None
    assert paired.robust.agrees
    assert paired.robust.method.endswith("Wilcoxon signed-rank")


def test_cluster_bootstrap_counts_clusters():
    rng = np.random.default_rng(4)
    shards = np.repeat([f"vm{i}" for i in range(12)], 3)
    b, c = rng.lognormal(0, 0.1, 36), rng.lognormal(0, 0.1, 36)
    e = es.continuous_effect(b, c, clusters=(shards, shards))
    assert e.n_clusters == 12
    assert "clusters" in e.method


def test_signed_metric_uses_difference():
    e = es.continuous_effect([-1.0, 0.5, 0.2, -0.3], [0.1, 0.8, 0.6, 0.4], scale="diff")
    assert e.scale == "diff"
    assert e.estimate == pytest.approx(
        np.mean([0.1, 0.8, 0.6, 0.4]) - np.mean([-1.0, 0.5, 0.2, -0.3])
    )


def test_log_scale_rejects_non_positive():
    with pytest.raises(ValueError, match="> 0"):
        es.continuous_effect([1.0, 0.0], [1.0, 2.0])


def test_too_few_samples():
    with pytest.raises(ValueError, match="too few"):
        es.continuous_effect([1.0], [1.0, 2.0])


def test_determinism():
    b, c = _lognormal_arms(20, 20)
    e1, e2 = es.continuous_effect(b, c), es.continuous_effect(b, c)
    assert e1 == e2
    assert np.array_equal(e1.bootstrap, e2.bootstrap)
    s1, s2 = es.shift_function(b, c), es.shift_function(b, c)
    assert np.array_equal(s1.low, s2.low)


def test_shift_function_sees_a_tail_move():
    rng = np.random.default_rng(5)
    b = rng.lognormal(0, 0.05, 60)
    c = rng.lognormal(0, 0.05, 60)
    c[np.argsort(c)[-15:]] *= 2.0
    sf = es.shift_function(b, c, scale="log")
    assert sf.low[-1] > 0
    assert sf.low[4] <= 0.05


def test_robust_check_without_scipy(monkeypatch):
    monkeypatch.setattr(es, "_have_scipy", lambda: False)
    b, c = _lognormal_arms(12, 12)
    e = es.continuous_effect(b, c)
    assert e.robust is not None
    assert "normal approx." in e.robust.method
    if st is not None:
        exact = st.mannwhitneyu(c, b, method="asymptotic", use_continuity=True).pvalue
        assert e.robust.p_value == pytest.approx(exact, rel=1e-6)
    p = es.proportion_effect([1] * 17 + [0], [1] * 18)
    assert "Fisher" in p.method


# --------------------------------------------------------------------------------------
# Binary effects.


def test_proportion_effect_17_of_18_to_18_of_18():
    p = es.proportion_effect([1] * 17 + [0], [1] * 18)
    assert p.estimate == pytest.approx(1 / 18)
    assert p.ci.low < 0 < p.ci.high
    assert p.bad_upper == pytest.approx(es.zero_event_upper(18))
    assert p.p_value > 0.1


def test_proportion_effect_paired_uses_mcnemar():
    p = es.proportion_effect([1, 0, 1, 1, 0], [1, 1, 1, 1, 1], paired=True)
    assert "McNemar" in p.method
    assert p.p_value == pytest.approx(es.mcnemar_exact_p(0, 2))


def test_proportion_rejects_non_binary():
    with pytest.raises(ValueError, match="0 or 1"):
        es.proportion_effect([0.5, 1], [1, 1])


# --------------------------------------------------------------------------------------
# Verdict table (spec §4.3), oriented so positive is better, margin 0.05.


@pytest.mark.parametrize(
    ("low", "high", "kind", "detail"),
    [
        (0.01, 0.20, VerdictKind.IMPROVED, None),
        (0.01, 0.05, VerdictKind.IMPROVED, None),  # touches Δ: counted as improved
        (-0.20, -0.01, VerdictKind.REGRESSED, None),
        (-0.04, 0.04, VerdictKind.EQUIVALENT, "no change"),
        (0.01, 0.04, VerdictKind.EQUIVALENT, "small gain"),
        (-0.04, -0.01, VerdictKind.EQUIVALENT, "small loss"),
        (-0.10, 0.03, VerdictKind.INCONCLUSIVE, None),
        (-0.02, 0.30, VerdictKind.INCONCLUSIVE, None),
        (0.0, 0.03, VerdictKind.EQUIVALENT, "no change"),  # L = 0 holds 0
    ],
)
def test_verdict_table(low, high, kind, detail):
    v = es.verdict(low, high, 0.05)
    assert v.kind == kind
    assert v.detail == detail
    assert v.glyph == es.GLYPHS[kind]


def test_noninferiority_flag():
    assert es.verdict(-0.04, 0.10, 0.05).noninferior
    assert not es.verdict(-0.06, 0.10, 0.05).noninferior


def test_mde_and_runs_needed():
    v = es.verdict(-0.1, 0.1, 0.05, se=0.06, n=6)
    assert v.mde == pytest.approx((es.norm_ppf(0.95) + es.norm_ppf(0.8)) * 0.06)
    assert v.underpowered
    assert v.mde is not None
    assert v.runs_needed is not None
    assert v.runs_needed == math.ceil(6 * (v.mde / 0.05) ** 2)
    assert v.add_runs == v.runs_needed - 6
    assert not es.verdict(-0.01, 0.01, 0.05, se=0.005, n=40).underpowered


def test_analyse_orients_a_minimised_metric():
    b, c = _lognormal_arms(20, 20, effect=-0.3)
    m = es.analyse("planning_time", b, c, direction="minimize")
    assert m.kind == "positive"
    assert m.verdict.kind == VerdictKind.IMPROVED
    m2 = es.analyse("throughput", b, c, direction="maximize")
    assert m2.verdict.kind == VerdictKind.REGRESSED


def test_apply_multiplicity_widens_primary_and_flags_secondary():
    rng = np.random.default_rng(9)
    metrics = [
        es.analyse(
            f"m{i}", rng.lognormal(0, 0.1, 20), rng.lognormal(-0.05 * i, 0.1, 20), primary=i < 3
        )
        for i in range(5)
    ]
    adjusted = es.apply_multiplicity(metrics)
    for before, after in zip(metrics[:3], adjusted[:3], strict=True):
        assert after.alpha == pytest.approx(0.05 / 3)
        assert after.holm_m == 3
        assert (
            after.effect.ci.high - after.effect.ci.low
            > before.effect.ci.high - before.effect.ci.low
        )
        assert after.adjusted_p is not None
    assert all(m.adjusted_p is not None for m in adjusted[3:])


# --------------------------------------------------------------------------------------
# Graphics: every graphic renders in both themes.


def _rows(metric, values, *, direction="minimize", inputs=None, order0=0, shards=None):
    return [
        {
            "metric": metric,
            "units": "s",
            "direction": direction,
            "repeat": i,
            "inputs": inputs or {},
            "value": float(v),
            "order": order0 + 2 * i,
            **({} if shards is None else {"shard": shards[i]}),
        }
        for i, v in enumerate(values)
    ]


def _evidence():
    rng = np.random.default_rng(11)
    base, cand = [], []
    base += _rows("planning_time", rng.lognormal(0, 0.1, 12))
    cand += _rows("planning_time", rng.lognormal(-0.2, 0.1, 12), order0=1)
    base += _rows("task_success", [1] * 11 + [0], direction="maximize")
    cand += _rows("task_success", [1] * 12, direction="maximize", order0=1)
    for x in (1, 2, 3):
        for y in ("a", "b"):
            shards = [f"vm{i % 2}" for i in range(10)]
            base += _rows(
                "sweep_time", rng.lognormal(0, 0.1, 10), inputs={"x": x, "y": y}, shards=shards
            )
            cand += _rows(
                "sweep_time",
                rng.lognormal(-0.1 * x, 0.1, 10),
                inputs={"x": x, "y": y},
                shards=shards,
            )
    for x in (1, 2, 3):
        base += _rows("line_time", rng.lognormal(0, 0.1, 10), inputs={"x": x})
        cand += _rows("line_time", rng.lognormal(-0.05 * x, 0.1, 10), inputs={"x": x})
    return base, cand


@pytest.fixture(scope="module")
def groups():
    base, cand = _evidence()
    groups, skipped = analyse_data(
        data_from_rows(base, cand), primary=["planning_time", "task_success"]
    )
    assert not skipped
    return {g.name: g for g in groups}


@pytest.mark.parametrize("theme", ig.THEMES, ids=lambda t: t.name)
def test_every_graphic_renders(groups, theme, tmp_path):
    from matplotlib.figure import Figure

    for i, fig in enumerate(_all_figures(groups, theme)):
        assert isinstance(fig, Figure)
        fig.savefig(tmp_path / f"g{i}.png", dpi=40)


def _all_figures(groups, theme):
    cont = groups["planning_time"].cells[0]
    binary = groups["task_success"].cells[0]
    sweep = sorted(groups["line_time"].cells, key=lambda m: m.point["x"])
    grid_cells = {(m.point["x"], m.point["y"]): m for m in groups["sweep_time"].cells}
    grid = [[grid_cells[(x, y)] for x in (1, 2, 3)] for y in ("a", "b")]
    return [
        ig.draw_scorecard([cont, binary], theme),
        ig.draw_forest(sweep, theme),
        ig.draw_estimation(cont, theme),
        ig.draw_raincloud_shift(cont, theme),
        ig.draw_waffle(binary, theme),
        ig.draw_sweep(sweep, [1, 2, 3], theme, x_name="x"),
        ig.draw_heatmap(grid, [1, 2, 3], ["a", "b"], theme, x_name="x", y_name="y"),
        ig.draw_power(cont, theme),
        ig.draw_diagnostics(cont, theme),
    ]


def _drawn_texts(fig):
    """Every text the figure draws: figure and axes texts, and the tick labels in view."""
    texts = list(fig.texts)
    for ax in fig.axes:
        texts += [*ax.texts, ax.xaxis.label, ax.yaxis.label]
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks():
                if lo - 1e-9 <= tick.get_loc() <= hi + 1e-9:
                    texts += [lab for lab in (tick.label1, tick.label2) if lab.get_visible()]
    return [t for t in texts if t.get_visible() and t.get_text().strip()]


def test_text_is_large_and_inside_the_figure(groups):
    """No text under 11 pt (15 px at the 800 px display width), none clipped at the edge."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    for fig in _all_figures(groups, ig.LIGHT):
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        box = fig.bbox
        for t in _drawn_texts(fig):
            assert t.get_fontsize() >= ig._MIN_PT, (t.get_text(), t.get_fontsize())
            ext = t.get_window_extent(renderer)
            inside = (
                ext.x0 >= box.x0 - 1
                and ext.x1 <= box.x1 + 1
                and ext.y0 >= box.y0 - 1
                and ext.y1 <= box.y1 + 1
            )
            assert inside, t.get_text()


def test_beeswarm_is_deterministic_and_keeps_dots_apart():
    rng = np.random.default_rng(3)
    y = rng.normal(0, 0.3, 40)
    d = 0.1
    a, b = ig._beeswarm(y, d, 5.0), ig._beeswarm(y, d, 5.0)
    assert np.array_equal(a, b)
    gaps = np.hypot(a[:, None] - a[None, :], y[:, None] - y[None, :])
    assert gaps[~np.eye(len(y), dtype=bool)].min() >= d * 0.99
    squeezed = ig._beeswarm(y, d, 0.05)
    assert np.abs(squeezed).max() <= 0.05 + 1e-12


def test_save_both_writes_png_at_2x_and_svg(groups, tmp_path):
    from matplotlib.image import imread

    paths = ig.save_both(
        lambda t: ig.draw_estimation(groups["planning_time"].cells[0], t), tmp_path, "est"
    )
    assert set(paths) == {"light", "dark", "light_svg", "dark_svg"}
    assert imread(paths["light"]).shape[1] == 1600
    assert paths["dark_svg"].read_text(encoding="utf-8").lstrip().startswith("<?xml")


def test_design_strip_facts(groups):
    m = groups["planning_time"].cells[0]
    facts = dict(ig.design_facts([m]))
    assert facts["design"] == "unpaired"
    assert facts["n"] == "12 / 12 per arm"
    assert facts["margin"].startswith("±5 %")
    assert "Holm ×2" in facts["test"]
    assert ig._order_pattern(ig._runs([m])) == "interleaved"
    shard_facts = dict(ig.design_facts(list(groups["sweep_time"].cells), points=6))
    assert shard_facts["design"] == "clustered by shard (2)"
    assert shard_facts["runs"] == "10 repeats × 6 points"


def test_headline_reads_as_the_finding(groups):
    m = groups["planning_time"].cells[0]
    assert ig.headline(m).startswith("Planning time is ")
    assert ig.headline(m).endswith("faster")
    assert "18/18" not in ig.headline(groups["task_success"].cells[0])
    assert "11/12 → 12/12" in ig.headline(groups["task_success"].cells[0])


# --------------------------------------------------------------------------------------
# The report.


def test_picture_has_dark_source_and_alt():
    html = picture("a.png", "b.png", 'x "quoted" & <b>')
    assert '<source media="(prefers-color-scheme: dark)" srcset="b.png">' in html
    assert 'alt="x &quot;quoted&quot; &amp; &lt;b>"' in html


def test_report_from_rows(tmp_path):
    base, cand = _evidence()
    report = report_from_rows(base, cand, tmp_path, primary=["planning_time"])
    md = (tmp_path / "evidence.md").read_text(encoding="utf-8")
    assert md == report.markdown
    assert md.startswith("## Evidence")
    assert md.count("<picture>") >= 5
    assert 'alt="Scorecard. Planning time: improved' in md
    assert "<details><summary>Method, diagnostics and data</summary>" in md
    assert "scorecard-dark.png" in md
    assert (tmp_path / "scorecard-light.svg").exists()
    assert "evidence-data.csv" in report.files
    # The facts the graphics no longer print are in the Markdown.
    assert "Design: unpaired; n 12 / 12 per arm" in md
    assert "in execution order (interleaved)" in md
    assert "The shaded band is the margin ±5 % around the base median" in md
    assert "Base 11/12 = 92 % (95 % Wilson CI" in md
    # Two metrics fit the scorecard: no forest plot.
    assert "forest-light.png" not in md
    linked = report.render("https://github.com/o/r/blob/abc/run")
    assert 'srcset="https://github.com/o/r/blob/abc/run/scorecard-dark.png"' in linked
    mapped = report.render({"scorecard-light.png": "https://x/y.png?raw=true"})
    assert 'src="https://x/y.png?raw=true"' in mapped


def test_evidence_rows_cli(tmp_path):
    from bencher.render import main

    base, cand = _evidence()
    (tmp_path / "b.json").write_text(json.dumps(base), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps(cand), encoding="utf-8")
    out = tmp_path / "rep"
    code = main(
        [
            "evidence-rows",
            str(tmp_path / "b.json"),
            str(tmp_path / "c.json"),
            "--report",
            str(out),
            "--primary",
            "planning_time",
            "--margin",
            "0.1",
        ]
    )
    assert code == 0
    md = (out / "evidence.md").read_text(encoding="utf-8")
    assert "±10 %" in md
    assert (
        main(
            [
                "evidence-rows",
                str(tmp_path / "missing.json"),
                str(tmp_path / "c.json"),
                "--report",
                str(out),
            ]
        )
        == 2
    )


class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=2)
    stop_distance = bn.ResultFloat(units="m", margin=0.1)
    stopped = bn.ResultBool()

    gain = 1.0
    rng = np.random.default_rng(0)

    def benchmark(self):
        self.stop_distance = Braking.gain * self.speed * Braking.rng.lognormal(0, 0.05)
        self.stopped = 1.0


def _bench_result(gain, seed):
    Braking.gain = gain
    Braking.rng = np.random.default_rng(seed)
    bench = bn.Bench(
        f"evidence_v2_{seed}", Braking(), run_cfg=bn.BenchRunCfg(repeats=4, cache_results=False)
    )
    return bench.plot_sweep(
        "braking",
        input_vars=["speed"],
        result_vars=["stop_distance", "stopped"],
        plot_callbacks=False,
    )


def test_report_from_recordings(tmp_path):
    base = _bench_result(1.0, 1)
    cand = _bench_result(0.7, 2)
    report = report_from_results(base, cand, tmp_path)
    names = {g.name: g for g in report.groups}
    assert names["stop_distance"].cells[0].margin == 0.1
    assert names["stopped"].cells[0].kind == "binary"
    assert len(names["stop_distance"].cells) == 2
    m = names["stop_distance"].cells[0]
    assert m.verdict.kind == VerdictKind.IMPROVED
    # Two recordings are a blocked design: every base run before every candidate run.
    assert ig._order_pattern(ig._runs([m])) == "blocked"
    assert "<picture>" in report.markdown
    assert "in execution order (blocked)" in report.markdown


def test_margin_is_excluded_from_the_hash():
    assert bn.ResultFloat(margin=0.1).hash_persistent() == bn.ResultFloat().hash_persistent()
    with pytest.raises(ValueError, match="margin"):
        bn.ResultFloat(margin=-1)


def _shard_rows(scale: float) -> list[dict]:
    return [
        {
            "metric": "t",
            "units": "s",
            "direction": "minimize",
            "repeat": r,
            "shard": f"vm{s}",
            "inputs": {},
            "value": scale * (1.0 + 0.01 * r + 0.1 * s),
        }
        for s in range(3)
        for r in range(3)
    ]


def test_paired_rows_pair_within_each_shard() -> None:
    """kbench shards reuse repeat ids 0..k, so pairing keys on (shard, repeat)."""
    ((base, cand),) = data_from_rows(_shard_rows(1.0), _shard_rows(0.9))[0].points.values()
    aligned = evidence_report._align(base, cand, paired=True)
    assert len(aligned.base) == 9
    assert np.allclose(aligned.cand / aligned.base, 0.9)


def test_paired_rows_reject_a_repeated_key() -> None:
    rows = _shard_rows(1.0)
    rows[1]["repeat"] = 0
    ((base, cand),) = data_from_rows(rows, _shard_rows(0.9))[0].points.values()
    with pytest.raises(ValueError, match="cannot pair"):
        evidence_report._align(base, cand, paired=True)
