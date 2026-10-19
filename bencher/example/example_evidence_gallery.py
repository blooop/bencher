"""A gallery of evidence reports (``docs/statistical_evidence.md``) from synthetic runs.

Each scenario makes base and candidate rows in the kbench row format and writes a
full report (``evidence.md`` plus light/dark PNG and SVG images) to its own
directory; ``index.md`` links them all::

    pixi run python bencher/example/example_evidence_gallery.py OUT_DIR
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from bencher.evidence_report import report_from_rows

SEED = 1178


def _rows(
    metric, units, direction, values, *, inputs=None, shards=None, start=0, order=None, seeds=None
):
    """Rows of one arm; *order* is each run's position in execution order (None: not recorded)."""
    return [
        {
            "metric": metric,
            "units": units,
            "direction": direction,
            "repeat": start + i,
            "inputs": dict(inputs or {}),
            "value": float(v),
            **({} if shards is None else {"shard": shards[i]}),
            **({} if order is None else {"order": int(order[i])}),
            **({} if seeds is None else {"seed": int(seeds[i])}),
        }
        for i, v in enumerate(values)
    ]


def _paired_lognormal(rng, n, median, cv, effect, pair_sd):
    """Paired timings: a shared per-pair machine factor plus small within-pair noise."""
    machine = rng.normal(0, pair_sd, n)
    base = median * np.exp(machine + rng.normal(0, cv, n))
    cand = median * (1 + effect) * np.exp(machine + rng.normal(0, cv, n))
    return base, cand


def _abba(n):
    """ABBA run order for n pairs: pair i runs base first when i is even, candidate first when odd."""
    base = [2 * i + (i % 2) for i in range(n)]
    cand = [2 * i + 1 - (i % 2) for i in range(n)]
    return base, cand


def _blocked(n_base, n_cand):
    return list(range(n_base)), list(range(n_base, n_base + n_cand))


def _bools(n, k, rng):
    out = np.array([1] * k + [0] * (n - k))
    rng.shuffle(out)
    return out


def scenario_improvement(rng):
    b, c = _paired_lognormal(rng, 20, 0.84, 0.05, -0.18, 0.25)
    sb, sc = _paired_lognormal(rng, 20, 31.0, 0.03, -0.004, 0.1)
    ob, oc = _abba(20)
    seeds = list(range(100, 120))
    kw_b = {"order": ob, "seeds": seeds}
    kw_c = {"order": oc, "seeds": seeds}
    rows_b = _rows("planning_time", "s", "minimize", b, **kw_b) + _rows(
        "task_duration", "s", "minimize", sb, **kw_b
    )
    rows_c = _rows("planning_time", "s", "minimize", c, **kw_c) + _rows(
        "task_duration", "s", "minimize", sc, **kw_c
    )
    return rows_b, rows_c, {"paired": True, "primary": ["planning_time", "task_duration"]}


def scenario_regression(rng):
    b = 12.0 * rng.lognormal(0, 0.06, 15)
    c = 12.0 * 1.12 * rng.lognormal(0, 0.06, 15)
    ob, oc = _blocked(15, 15)
    return (
        _rows("task_duration", "s", "minimize", b, order=ob),
        _rows("task_duration", "s", "minimize", c, order=oc),
        {"primary": ["task_duration"]},
    )


def scenario_equivalence(rng):
    names = [
        "tracking_error_rms",
        "planning_time",
        "task_duration",
        "plan_requests",
        "orphan_count_rate",
    ]
    rows_b, rows_c = [], []
    for i, name in enumerate(names):
        base_level = [0.031, 0.84, 31.0, 14.0, 2.5][i]
        b = base_level * rng.lognormal(0, 0.03, 30)
        c = base_level * (1 + [0.004, -0.006, 0.002, 0.01, -0.012][i]) * rng.lognormal(0, 0.03, 30)
        ob = [2 * k for k in range(30)]
        oc = [2 * k + 1 for k in range(30)]
        shards = [f"vm{k % 3}" for k in range(30)]
        unit = "s" if "time" in name or "duration" in name else ""
        rows_b += _rows(name, unit, "minimize", b, order=ob, shards=shards)
        rows_c += _rows(name, unit, "minimize", c, order=oc, shards=shards)
    return rows_b, rows_c, {"primary": ["tracking_error_rms"]}


def scenario_inconclusive(rng):
    b = 2.4 * rng.lognormal(0, 0.15, 6)
    c = 2.4 * 0.96 * rng.lognormal(0, 0.15, 6)
    return (
        _rows("time_to_goal", "s", "minimize", b),
        _rows("time_to_goal", "s", "minimize", c),
        {"primary": ["time_to_goal"]},
    )


def scenario_success_rate(rng):
    ob, oc = _blocked(18, 18)
    rows_b = _rows("task_success", "", "maximize", _bools(18, 17, rng), order=ob)
    rows_b += _rows("required_sigkill", "", "minimize", _bools(18, 3, rng), order=ob)
    rows_c = _rows("task_success", "", "maximize", _bools(18, 18, rng), order=oc)
    rows_c += _rows("required_sigkill", "", "minimize", _bools(18, 0, rng), order=oc)
    return rows_b, rows_c, {"primary": ["task_success", "required_sigkill"]}


def scenario_flake_fixed(rng):
    return (
        _rows("clean_exit", "", "maximize", _bools(30, 26, rng), order=list(range(0, 60, 2))),
        _rows("clean_exit", "", "maximize", _bools(30, 30, rng), order=list(range(1, 60, 2))),
        {"primary": ["clean_exit"]},
    )


def scenario_heavy_tail(rng):
    n = 40
    b = 0.20 * rng.lognormal(0, 0.05, n)
    c = 0.20 * rng.lognormal(0, 0.05, n)
    # The slowest quarter of candidate requests hits a slow path: the median holds, p90/p95 move.
    slow = np.argsort(c)[-n // 4 :]
    c[slow] *= rng.uniform(1.5, 2.2, len(slow))
    ob, oc = _blocked(n, n)
    return (
        _rows("request_latency", "s", "minimize", b, order=ob),
        _rows("request_latency", "s", "minimize", c, order=oc),
        {"primary": ["request_latency"]},
    )


def scenario_sweep_1d(rng):
    rows_b, rows_c = [], []
    for p, speed in enumerate((0.5, 1.0, 1.5, 2.0, 2.5, 3.0)):
        ob = [24 * p + 2 * k for k in range(12)]
        oc = [24 * p + 2 * k + 1 for k in range(12)]
        base = 0.6 + 0.35 * speed
        gain = -0.12 if speed >= 2.0 else -0.01 * speed
        rows_b += _rows(
            "stop_distance",
            "m",
            "minimize",
            base * rng.lognormal(0, 0.05, 12),
            inputs={"speed": speed},
            order=ob,
        )
        rows_c += _rows(
            "stop_distance",
            "m",
            "minimize",
            base * (1 + gain) * rng.lognormal(0, 0.05, 12),
            inputs={"speed": speed},
            order=oc,
        )
    return rows_b, rows_c, {}


def scenario_sweep_2d(rng):
    rows_b, rows_c = [], []
    point = 0
    for load in (1, 2, 4, 8):
        for planner in ("rrt", "prm", "cbs"):
            ob = [24 * point + 2 * k for k in range(12)]
            oc = [24 * point + 2 * k + 1 for k in range(12)]
            point += 1
            base = 0.4 * load**0.6 * {"rrt": 1.0, "prm": 1.3, "cbs": 0.8}[planner]
            eff = {"rrt": -0.15, "prm": 0.0, "cbs": 0.08}[planner] * (load / 4) ** 0.5
            shards = [f"vm{i % 3}" for i in range(12)]
            rows_b += _rows(
                "planning_time",
                "s",
                "minimize",
                base * rng.lognormal(0, 0.06, 12),
                inputs={"load": load, "planner": planner},
                shards=shards,
                order=ob,
            )
            rows_c += _rows(
                "planning_time",
                "s",
                "minimize",
                base * (1 + eff) * rng.lognormal(0, 0.06, 12),
                inputs={"load": load, "planner": planner},
                shards=shards,
                order=oc,
            )
    return rows_b, rows_c, {}


SCENARIOS = {
    "improvement": ("A clear improvement, paired n=20", scenario_improvement),
    "regression": ("A regression, unpaired n=15", scenario_regression),
    "equivalence": ("Equivalence: five metrics inside ±5 %", scenario_equivalence),
    "inconclusive": ("Inconclusive: n=6 cannot see a 4 % change", scenario_inconclusive),
    "success-rate": ("Binary rates: 17/18 → 18/18 and 3/18 → 0/18", scenario_success_rate),
    "flake-fixed": ("Flake fixed: 0 failures in 30 runs", scenario_flake_fixed),
    "heavy-tail": ("Heavy-tailed latency: the median holds, p95 moves", scenario_heavy_tail),
    "sweep-1d": ("A 1-D sweep over speed", scenario_sweep_1d),
    "sweep-2d": ("A 2-D sweep: load × planner, clustered by VM", scenario_sweep_2d),
}


def example_evidence_gallery(out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = ["# Evidence gallery\n"]
    for slug, (title, make) in SCENARIOS.items():
        rng = np.random.default_rng(SEED)
        base, cand, opts = make(rng)
        report = report_from_rows(base, cand, out / slug, **opts)
        index.append(f"- [{title}]({slug}/{report.markdown_path.name})")
    path = out / "index.md"
    path.write_text("\n".join(index) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "evidence-gallery"
    print(example_evidence_gallery(target))
