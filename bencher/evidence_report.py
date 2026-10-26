"""The PR evidence report of ``docs/statistical_evidence.md`` §6: Markdown plus image files.

Two sources feed it, through one intermediate (:class:`MetricData`):

* two bencher recordings (:func:`data_from_results`, the ``bencher.render.load_result``
  pickles): every scalar result variable both sides have, with the sweep inputs as
  the points and ``repeat`` as the samples, from the last ``over_time`` snapshot;
* two kbench row files (:func:`data_from_rows`): a JSON list of
  ``{metric, units, direction, repeat, inputs, value}`` rows, optionally with a
  ``shard`` (the cluster of the cluster bootstrap), an ``order`` or ``timestamp``
  (the run order the graphics draw as rows of squares) and a ``seed``.

:func:`analyse_data` runs :mod:`bencher.evidence_stats` on every metric and point,
Holm over the primary metrics and Benjamini–Hochberg over the rest.
:func:`write_report` draws the graphics (:mod:`bencher.infographic`) in both
themes and writes ``evidence.md``: the scorecard, a one-line summary, the forest
plot, one section per primary or moving metric, the sweeps, and a ``<details>``
block with the method, the diagnostics and the data as CSV. Each image is a
``<picture>`` with a dark source and alt text that carries the verdict and the
numbers. The pictures link the animated SVGs by default (GitHub serves a blob's
``?raw=true`` SVG as ``image/svg+xml``); ``svg=False`` links the still PNGs for a host
that does not serve SVG as an image.

Image links default to paths relative to the report. *url_base* takes a URL
prefix, a ``{file name: URL}`` mapping (what
:func:`bencher.evidence_ref.publish_evidence` returns) or a callable; or write
first, push :attr:`Report.files`, and call :meth:`Report.render` again with the
links.
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from bencher import infographic as ig
from bencher.evidence_stats import (
    ALPHA,
    Direction,
    Effect,
    MetricEvidence,
    MetricKind,
    ProportionEffect,
    VerdictKind,
    analyse,
    apply_multiplicity,
    shift_function,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bencher.results.bench_result import BenchResult

UrlBase = str | Mapping[str, str] | Callable[[str], str] | None
# Scorecard tiles when no primary metric is named: the metrics that moved, first.
MAX_TILES = 6
# The forest plot is drawn only for more metrics than this; fewer fit the scorecard.
MAX_FOREST_ROWS = 4


@dataclass
class Arm:
    """The samples of one arm at one point: values, repeat ids, clusters (shards), run order, seeds.

    *orders* holds each sample's run order (an index or a timestamp) or ``None``
    when the source did not record it; *seeds* the seed of each run, when known.
    """

    values: list[float] = field(default_factory=list)
    repeats: list[Any] = field(default_factory=list)
    clusters: list[Any] = field(default_factory=list)
    orders: list[float | None] = field(default_factory=list)
    seeds: list[Any] = field(default_factory=list)


@dataclass
class MetricData:
    """One metric's samples per input point, for both arms."""

    name: str
    units: str = ""
    direction: Direction = "minimize"
    kind: MetricKind | None = None
    margin: float | None = None
    inputs: tuple[str, ...] = ()
    points: dict[tuple, tuple[Arm, Arm]] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricGroup:
    """The analysed cells of one metric: one cell when nothing was swept."""

    name: str
    inputs: tuple[str, ...]
    cells: tuple[MetricEvidence, ...]

    @property
    def swept(self) -> bool:
        return len(self.cells) > 1 or bool(self.inputs)


# --------------------------------------------------------------------------------------
# Loading.


def _direction(value: object) -> Direction:
    text = str(getattr(value, "value", value)).lower()
    return "maximize" if text.startswith("max") else "minimize"


def data_from_rows(base_rows: Sequence[Mapping], cand_rows: Sequence[Mapping]) -> list[MetricData]:
    """Group kbench rows by metric and input point; ``shard`` (if any) is the cluster."""
    metrics: dict[str, MetricData] = {}
    for arm_index, rows in ((0, base_rows), (1, cand_rows)):
        for row in rows:
            name = str(row["metric"])
            inputs = dict(row.get("inputs") or {})
            md = metrics.get(name)
            if md is None:
                md = MetricData(
                    name=name,
                    units=str(row.get("units") or ""),
                    direction=_direction(row.get("direction", "minimize")),
                    inputs=tuple(sorted(inputs)),
                )
                metrics[name] = md
            point = tuple(inputs.get(k) for k in md.inputs)
            arms = md.points.setdefault(point, (Arm(), Arm()))
            value = row.get("value")
            arm = arms[arm_index]
            arm.values.append(float("nan") if value is None else float(value))
            arm.repeats.append(row.get("repeat", len(arm.repeats)))
            arm.clusters.append(row.get("shard"))
            order = row.get("order", row.get("timestamp"))
            arm.orders.append(None if order is None else _order_value(order))
            arm.seeds.append(row.get("seed"))
    return list(metrics.values())


def _order_value(value: object) -> float:
    """A run order as a number: an index as is, an ISO timestamp as epoch seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    from datetime import datetime

    return datetime.fromisoformat(str(value)).timestamp()


def load_rows(path: str | Path) -> list[dict]:
    """Read a kbench row file: a JSON list of rows (or ``{"rows": [...]}``)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected a JSON list of rows")  # noqa: TRY004 - bad input file, not a bad argument
    return rows


def data_from_results(baseline: BenchResult, candidate: BenchResult) -> list[MetricData]:
    """The scalar result variables both recordings have, per sweep point, over ``repeat``."""
    from bencher.report_export import _snapshot_ds
    from bencher.variables.results import ResultBool, ResultFloat

    base_ds, cand_ds = _snapshot_ds(baseline), _snapshot_ds(candidate)
    base_names = {rv.name for rv in baseline.bench_cfg.result_vars}
    out = []
    for rv in candidate.bench_cfg.result_vars:
        if not isinstance(rv, ResultFloat) or rv.name not in base_names:
            continue
        if rv.name not in base_ds or rv.name not in cand_ds:
            continue
        md = MetricData(
            name=rv.name,
            units="" if rv.units == "ul" else rv.units,
            direction=_direction(rv.direction),
            kind="binary" if isinstance(rv, ResultBool) else None,
            margin=getattr(rv, "margin", None),
        )
        das = []
        for ds in (base_ds, cand_ds):
            da = ds[rv.name]
            dims = [d for d in da.dims if d != "repeat"]
            das.append(
                da.transpose(*dims, "repeat")
                if "repeat" in da.dims
                else da.expand_dims("repeat", -1)
            )
        dims = tuple(d for d in das[1].dims if d != "repeat")
        md.inputs = tuple(str(d) for d in dims)
        for arm_index, da in enumerate(das):
            coords = [da.coords[d].values for d in dims] if dims else []
            values = np.asarray(da.values, dtype=float)
            # Two recordings are two runs: base first, then candidate (a blocked design).
            # Within a run the repeat index is the order bencher ran the samples in.
            offset = 0 if arm_index == 0 else das[0].sizes["repeat"]
            for idx in np.ndindex(*values.shape[:-1]):
                point = tuple(_plain(coords[i][j]) for i, j in enumerate(idx))
                arms = md.points.setdefault(point, (Arm(), Arm()))
                samples = values[idx]
                arm = arms[arm_index]
                arm.values.extend(samples.tolist())
                arm.repeats.extend(range(len(samples)))
                arm.clusters.extend([None] * len(samples))
                arm.orders.extend(float(offset + r) for r in range(len(samples)))
                arm.seeds.extend([None] * len(samples))
        out.append(md)
    if not out:
        raise ValueError("the two recordings share no scalar result variable")
    return out


def _plain(value: object) -> object:
    item = getattr(value, "item", None)
    return item() if callable(item) else value


# --------------------------------------------------------------------------------------
# Analysis.


@dataclass(frozen=True)
class _Aligned:
    base: np.ndarray
    cand: np.ndarray
    clusters: tuple[np.ndarray | None, np.ndarray | None]
    order: tuple[np.ndarray | None, np.ndarray | None]
    seed_policy: str | None


def _orders(values: Sequence[float | None]) -> np.ndarray | None:
    if not values or any(v is None for v in values):
        return None
    return np.asarray(values, dtype=float)


def _seed_policy(base: Sequence[Any], cand: Sequence[Any], paired: bool) -> str | None:
    if any(s is None for s in [*base, *cand]):
        return None
    if paired and list(base) == list(cand):
        return "same seed per pair"
    distinct = len({*map(str, base), *map(str, cand)})
    return f"{distinct} seeds recorded"


def _pair_index(arm: Arm) -> dict[tuple[Any, Any], int]:
    index: dict[tuple[Any, Any], int] = {}
    for i, key in enumerate(zip(arm.clusters, arm.repeats, strict=True)):
        if key in index:
            msg = f"cannot pair: shard {key[0]!r} has repeat {key[1]!r} twice"
            raise ValueError(msg)
        index[key] = i
    return index


def _align(base: Arm, cand: Arm, paired: bool) -> _Aligned:
    """The arm arrays the stats read; paired arms are matched by (shard, repeat id).

    kbench shards each count their repeats from 0, so the repeat id alone is not a key.
    A key that repeats inside one arm cannot pair, and raises.
    """
    if paired:
        b_by = _pair_index(base)
        c_by = _pair_index(cand)
        keys = sorted(set(b_by) & set(c_by), key=str)
        bi, ci = [b_by[k] for k in keys], [c_by[k] for k in keys]
    else:
        bi, ci = list(range(len(base.values))), list(range(len(cand.values)))
    b = np.asarray(base.values, dtype=float)[bi]
    c = np.asarray(cand.values, dtype=float)[ci]
    cl_b = [base.clusters[i] for i in bi]
    cl_c = [cand.clusters[i] for i in ci]
    clusters: tuple[np.ndarray | None, np.ndarray | None] = (None, None)
    if any(x is not None for x in cl_b + cl_c):
        clusters = (
            np.asarray(cl_b, dtype=object).astype(str),
            np.asarray(cl_c, dtype=object).astype(str),
        )
    order = (_orders([base.orders[i] for i in bi]), _orders([cand.orders[i] for i in ci]))
    seeds = _seed_policy([base.seeds[i] for i in bi], [cand.seeds[i] for i in ci], paired)
    return _Aligned(b, c, clusters, order, seeds)


def analyse_data(
    data: Sequence[MetricData],
    *,
    primary: Sequence[str] = (),
    margin: float | None = None,
    paired: bool = False,
) -> tuple[list[MetricGroup], list[str]]:
    """Analyse every metric and point; return the groups and the metrics skipped (with why)."""
    cells: list[MetricEvidence] = []
    owner: list[str] = []
    skipped: list[str] = []
    for md in data:
        for point, (base, cand) in md.points.items():
            al = _align(base, cand, paired)
            try:
                ev = analyse(
                    md.name,
                    al.base,
                    al.cand,
                    direction=md.direction,
                    units=md.units,
                    kind=md.kind,
                    margin=margin if margin is not None else md.margin,
                    paired=paired,
                    clusters=al.clusters,
                    primary=md.name in primary,
                    point=dict(zip(md.inputs, point, strict=True)),
                    order=al.order,
                    seed_policy=al.seed_policy,
                )
            except ValueError as exc:
                where = (
                    f" at {_point_label(dict(zip(md.inputs, point, strict=True)))}"
                    if md.inputs
                    else ""
                )
                skipped.append(f"`{md.name}`{where}: {exc}")
                continue
            cells.append(ev)
            owner.append(md.name)
    cells = apply_multiplicity(cells)
    groups = []
    for md in data:
        mine = tuple(c for c, o in zip(cells, owner, strict=True) if o == md.name)
        if mine:
            groups.append(MetricGroup(md.name, md.inputs, mine))
    return groups, skipped


def _point_label(point: Mapping[str, object]) -> str:
    return ", ".join(f"{k}={v}" for k, v in point.items())


# --------------------------------------------------------------------------------------
# The report.


@dataclass
class Report:
    """The written report: Markdown, the image files and the analysed metrics."""

    out_dir: Path
    groups: list[MetricGroup]
    files: dict[str, Path]
    sections: list[Callable[[Callable[[str], str]], str]]
    skipped: list[str] = field(default_factory=list)
    markdown_path: Path | None = None
    markdown: str = ""
    svg: bool = True

    def render(self, url_base: UrlBase = None, *, svg: bool | None = None) -> str:
        """The Markdown with every image linked through *url_base*; also rewrites the file.

        *svg* (default: as last rendered, first True) links each graphic's animated SVG;
        False links its still PNG.
        """
        if svg is not None:
            self.svg = svg
        link = _url_for(url_base)

        def url_for(name: str) -> str:
            twin = name.removesuffix(".png") + ".svg"
            if self.svg and name.endswith(".png") and twin in self.files:
                return link(twin)
            return link(name)

        self.markdown = "\n".join(section(url_for) for section in self.sections).rstrip() + "\n"
        if self.markdown_path is not None:
            self.markdown_path.write_text(self.markdown, encoding="utf-8")
        return self.markdown


def _url_for(url_base: UrlBase) -> Callable[[str], str]:
    if url_base is None:
        return lambda name: name
    if isinstance(url_base, str):
        prefix = url_base.rstrip("/")
        return lambda name: f"{prefix}/{name}"
    if isinstance(url_base, Mapping):
        mapping = url_base
        return lambda name: mapping.get(name, name)
    return url_base


def picture(light: str, dark: str, alt: str, width: int = ig.ONE_PX) -> str:
    """A GitHub ``<picture>`` with a dark-mode source and the light image as fallback."""
    alt_attr = alt.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{dark}">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="{light}">\n'
        f'  <img alt="{alt_attr}" src="{light}" width="{width}">\n'
        "</picture>\n"
    )


class _Images:
    """Draws graphics into the report directory and remembers their file names."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.files: dict[str, Path] = {}

    def add(
        self, stem: str, draw: Callable[[ig.Theme], Any], alt: str
    ) -> Callable[[Callable[[str], str]], str]:
        paths = ig.save_both(draw, self.out_dir, stem)
        for path in paths.values():
            self.files[path.name] = path
        light, dark = paths["light"].name, paths["dark"].name
        width = ig.display_px(paths["light"])
        return lambda url_for: picture(url_for(light), url_for(dark), alt, width)


def _slug(text: str) -> str:
    out = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "metric"


def _moved(m: MetricEvidence) -> bool:
    return m.verdict.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED)


def _forest_key(rows: Sequence[MetricEvidence]) -> str:
    key = (
        "Rows are sorted by effect. Left: every run of each row (grey base above, blue "
        "candidate below, a tick at the median, on the row's own scale). Right: the change "
        f"as a dot over the shaded margin {ig.fmt_margin(rows[0])}; a dashed line from 0 "
        "leads to each ▲/▼ estimate, and a still one to each ? estimate. Bold rows are "
        "primary metrics."
    )
    if any(not m.fdr_pass for m in rows):
        key += " A hollow dot fails the FDR check."
    return key


def _ci_line(
    cells: Sequence[MetricEvidence], labels: Sequence[str] | None = None, *, units: bool = False
) -> str:
    """The CIs the graphic does not draw, exact: ``90 % CI: `a` −17.8 … −13.1 %; …``.

    With *units* (the views of one metric each), a metric shown in its units gets the CI
    in units first and the % CI after it: ``−0.13 … −0.10 s (−17.8 … −13.1 %)``.
    """
    names = labels if labels is not None else [f"`{m.name}`" for m in cells]
    parts = []
    for name, m in zip(names, cells, strict=True):
        level, _, rest = ig.fmt_ci(m).partition(" CI ")
        if units and ig.in_units(m):
            rest = f"{ig.fmt_change_ci(m).partition(' CI ')[2]} ({rest})"
        parts.append((level, f"{name} {rest}"))
    levels = sorted({lv for lv, _ in parts})
    if len(levels) == 1:
        return f"{levels[0]} CI: " + "; ".join(p for _, p in parts) + ".\n"
    return "CI: " + "; ".join(f"{p} ({lv})" for lv, p in parts) + ".\n"


def _tile_metrics(singles: Sequence[MetricEvidence]) -> list[MetricEvidence]:
    prim = [m for m in singles if m.primary]
    if prim:
        return prim
    rank = {
        VerdictKind.IMPROVED: 0,
        VerdictKind.REGRESSED: 0,
        VerdictKind.INCONCLUSIVE: 1,
        VerdictKind.EQUIVALENT: 2,
    }
    return sorted(singles, key=lambda m: (rank[m.verdict.kind], -abs(m.effect.estimate)))[
        :MAX_TILES
    ]


def _design(cells: Sequence[MetricEvidence], primary: int) -> str:
    paired = any(m.paired for m in cells)
    ns = sorted({min(m.effect.n_base, m.effect.n_cand) for m in cells})
    n = f"n={ns[0]}" if len(ns) == 1 else f"n={ns[0]}–{ns[-1]}"
    margins = sorted({ig.fmt_margin(m) for m in cells})
    parts = ["paired" if paired else "unpaired", n, f"margin {', '.join(margins)}"]
    if primary:
        parts.append(f"Holm over {primary} primary metric{'s' if primary != 1 else ''}")
    parts.append("BH at q = 0.05 over the rest")
    return ", ".join(parts)


def _vm_names(cells: Sequence[MetricEvidence]) -> str:
    names = ig.shard_names(cells)
    return ", ".join(f"VM {k + 1} = `{s}`" for k, s in enumerate(names))


def _order_note(
    cells: Sequence[MetricEvidence],
    *,
    where: str = "under the panels",
    order: ig.OrderMode = "auto",
) -> str:
    """What the run-order rows show, or the design in one line when the graphic has none."""
    if not ig.order_recorded(cells):
        return (
            "The run order was not recorded, so the graphic has no run-order row "
            f"(design: {ig.design_sentence(cells)})."
        )
    if not ig.show_order(cells, order):
        return f"Design: {ig.design_sentence(cells)}."
    vms = _vm_names(cells)
    rows = f", one row per VM ({vms})" if vms else ""
    return (
        f"The squares {where} are the runs in execution order ({ig.order_pattern(cells)})"
        f"{rows}: grey base, blue candidate."
    )


def _arms_key(cells: Sequence[MetricEvidence]) -> str:
    """How to read the arms panels of the scorecard and the estimation plot."""
    margins = ", ".join(sorted({ig.fmt_margin(m) for m in cells}))
    parts = []
    if any(isinstance(m.effect, Effect) for m in cells):
        parts.append(
            "Each dot is one run: grey base, blue candidate; the thick bar is each arm's "
            f"median. The shaded band is the margin {margins} around the base median. The "
            "dashed line between the columns runs from the base median to the candidate "
            "median, in the verdict colour."
        )
        if any(m.paired for m in cells):
            parts.append(
                "Faint lines join the two runs of a pair: green when the pair got better, "
                "orange when it got worse."
            )
    if any(isinstance(m.effect, ProportionEffect) for m in cells):
        parts.append(
            "For a pass/fail metric each square is one run; a crossed orange square is a bad "
            "outcome, and a dashed outline marks the candidate runs whose outcome differs "
            "from base."
        )
    return " ".join(parts)


def _design_line(cells: Sequence[MetricEvidence], *, points: int = 1) -> str:
    facts = ig.design_facts(cells, points=points)
    return "Design: " + "; ".join(v if k == "design" else f"{k} {v}" for k, v in facts) + "."


def _effect_sentence(m: MetricEvidence) -> str:
    e = m.effect
    point = f" at {_point_label(m.point)}" if m.point else ""
    if isinstance(e, ProportionEffect):
        text = (
            f"`{m.name}`{point} {ig.fmt_counts(e)}, difference {ig.fmt_effect(m)} "
            f"[{ig.fmt_ci(m)}], {e.method}, {_p(e.p_value)}."
        )
        text += (
            f" Base {e.k_base}/{e.n_base} = {100 * e.p_base:.0f} % (95 % Wilson CI "
            f"{100 * e.wilson_base.low:.0f}–{100 * e.wilson_base.high:.0f} %), candidate "
            f"{e.k_cand}/{e.n_cand} = {100 * e.p_cand:.0f} % "
            f"({100 * e.wilson_cand.low:.0f}–{100 * e.wilson_cand.high:.0f} %)."
        )
        bad = e.n_cand - e.k_cand if m.direction == "maximize" else e.k_cand
        if bad == 0:
            bound = ig.worst_plausible(m)
            text += (
                f" No bad outcome in {e.n_cand} candidate runs: its rate is at most "
                f"{100 * e.bad_upper:.1f} % (95 %, exact; rule of three {300 / e.n_cand:.1f} %)."
                f" The black tick on the difference axis is that bound: a difference of "
                f"{ig.fmt_signed(100 * (bound or 0.0))} pp."
            )
        else:
            text += (
                f" The candidate's bad-outcome rate is at most {100 * e.bad_upper:.1f} % "
                "(95 % upper bound, exact)."
            )
        return text
    cis = ig.fmt_ci(m)
    if e.ci95.level > e.ci.level:
        cis += f"; {ig.fmt_ci(m, level95=True)}"
    text = f"`{m.name}`{point} {ig.fmt_effect(m)} [{cis}]"
    if ig.in_units(m):
        unit_cis = ig.fmt_change_ci(m)
        if e.ci95.level > e.ci.level:
            unit_cis += f"; {ig.fmt_change_ci(m, level95=True)}"
        text = (
            f"`{m.name}`{point} {ig.fmt_change(m)} [{unit_cis}], that is {ig.fmt_effect(m)} [{cis}]"
        )
    text += f", {e.method}, n={e.n_base}"
    text += " pairs" if e.paired else f"/{e.n_cand}"
    if e.n_clusters:
        text += f" in {e.n_clusters} shards"
    text += "."
    if ig.in_units(m):
        text += (
            f" The test is on the ratio; the change in {m.units.strip()} is that ratio and its CI "
            f"at the base median {ig.fmt_base_median(m)}: base median × (ratio − 1)."
        )
    if m.verdict.mde is not None:
        text += f" MDE {ig.fmt_mde(m)} at 80 % power."
    if e.robust is not None:
        r = e.robust
        verb = "agrees" if r.agrees else "**disagrees**"
        text += f" {r.method.split(' + ')[-1]} {verb} ({_p(r.p_value)})."
    return text


def _p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"  # noqa: PLR2004


def _needs_shift(m: MetricEvidence) -> bool:
    """Whether to show the raincloud + shift function for *m*.

    Yes when the rank check disagrees, or when a decile from p70 up moved (its CI
    excludes 0) by more than Δ beyond the median's move.
    """
    e = m.effect
    if not isinstance(e, Effect):
        return False
    if e.robust is not None and not e.robust.agrees:
        return True
    min_tail_n = 15
    if min(e.n_base, e.n_cand) < min_tail_n:
        return False
    sf = shift_function(
        m.base, m.cand, scale="log" if m.kind == "positive" else "diff", paired=m.paired
    )
    delta = math.log1p(m.margin) if m.kind == "positive" else m.margin
    middle = sf.probs.index(0.5)
    upper = [i for i, p in enumerate(sf.probs) if p >= 0.7]  # noqa: PLR2004
    return any(
        (sf.low[i] > 0 or sf.high[i] < 0) and abs(sf.diff[i] - sf.diff[middle]) > delta
        for i in upper
    )


def _csv(groups: Sequence[MetricGroup]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["metric", "point", "arm", "index", "value"])
    for g in groups:
        for m in g.cells:
            for arm, vals in (("base", m.base), ("candidate", m.cand)):
                for i, v in enumerate(vals):
                    w.writerow([m.name, _point_label(m.point), arm, i, f"{v:.6g}"])
    return buf.getvalue()


def _verdict_table(cells: Sequence[MetricEvidence]) -> str:
    lines = [
        "| Metric | Point | Effect | 90 % CI | Verdict | adj. p |",
        "|---|---|---|---|---|---|",
    ]
    for m in cells:
        ci = ig.fmt_ci(m).split("CI ")[-1]
        adj = "" if m.adjusted_p is None else _p(m.adjusted_p)
        flag = "" if m.fdr_pass else " (fails FDR)"
        lines.append(
            f"| `{m.name}` | {_point_label(m.point)} | {ig.fmt_effect(m)} | {ci} | {ig.verdict_label(m)}{flag} | {adj} |"
        )
    return "\n".join(lines) + "\n"


def write_report(
    groups: Sequence[MetricGroup],
    out_dir: str | Path,
    *,
    url_base: UrlBase = None,
    title: str = "Evidence",
    skipped: Sequence[str] = (),
    diagnostics: bool = True,
    svg: bool = True,
    order: ig.OrderMode = "auto",
) -> Report:
    """Draw every graphic into *out_dir* and write ``evidence.md`` there (spec §6).

    *order* says when a graphic draws the run-order strip: ``"auto"`` (only when the
    design is not simple, see :func:`bencher.infographic.simple_design`), ``"always"``
    or ``"never"``. Without the strip the caption states the design in one line.
    """
    if order not in ig.ORDER_MODES:
        raise ValueError(f"order must be one of {ig.ORDER_MODES}, not {order!r}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = _Images(out)
    sections: list[Callable[[Callable[[str], str]], str]] = []

    def text(s: str) -> None:
        sections.append(lambda _u: s)

    cells = [m for g in groups for m in g.cells]
    if not cells:
        raise ValueError("write_report: no metric could be analysed")
    singles = [g.cells[0] for g in groups if not g.swept]
    n_primary = len({g.name for g in groups if any(m.primary for m in g.cells)})
    text(f"## {title}\n")
    summary = ig.summary_counts(cells)
    tiles = _tile_metrics(singles)
    if tiles:
        alt = "Scorecard. " + " ".join(ig.alt_text(m) for m in tiles)
        sections.append(
            img.add("scorecard", lambda t: ig.draw_scorecard(tiles, t, order=order), alt)
        )
    if tiles:
        text(_ci_line(tiles, units=True))
    text(f"**{summary}** — {_design(cells, n_primary)}.\n")
    if tiles:
        text(f"*{_arms_key(tiles)} {_order_note(tiles[:1], order=order)}*\n")
    for kinds, stem in ((("positive",), "forest"), (("binary", "fraction"), "forest-rates")):
        rows = [m for m in singles if m.kind in kinds]
        if len(rows) > MAX_FOREST_ROWS:
            alt = "Forest plot. " + " ".join(ig.alt_text(m) for m in rows)
            sections.append(
                img.add(stem, lambda t, rows=rows: ig.draw_forest(rows, t, order=order), alt)
            )
            text(_ci_line(rows))
            text(f"*{_forest_key(rows)}*\n")
    # One section per primary metric, and per secondary metric that did not stay equivalent.
    shown = [m for m in singles if m.primary or m.verdict.kind != VerdictKind.EQUIVALENT]
    shown.sort(key=lambda m: (not m.primary, m.name))
    for m in shown:
        stem = _slug(m.name)
        text(f"### {ig.headline(m)} {m.verdict.glyph}\n")
        if isinstance(m.effect, ProportionEffect):
            sections.append(
                img.add(
                    f"{stem}-waffle",
                    lambda t, m=m: ig.draw_waffle(m, t, order=order),
                    ig.alt_text(m),
                )
            )
        else:
            sections.append(
                img.add(
                    f"{stem}-estimation",
                    lambda t, m=m: ig.draw_estimation(m, t, order=order),
                    ig.alt_text(m),
                )
            )
        design = "" if ig.show_order([m], order) else f" Design: {ig.design_sentence([m])}."
        text(_effect_sentence(m) + design + "\n")
        if _needs_shift(m):
            sections.append(
                img.add(
                    f"{stem}-shift",
                    lambda t, m=m: ig.draw_raincloud_shift(m, t),
                    "Raincloud and shift function. " + ig.alt_text(m),
                )
            )
            per = (
                f" in {m.units.strip()} (candidate decile − base decile)" if ig.in_units(m) else ""
            )
            text(
                "The rank check or a tail decile disagrees with the mean: read the shift function above, not one number. "
                "Top: each arm's density, box (quartiles, median ring) and every run. Bottom: the change "
                f"at each decile q1…q9{per}, coloured where its 95 % bootstrap CI excludes 0: "
                f"{ig.shift_summary(m)}.\n"
            )
        if m.verdict.underpowered and m.verdict.kind not in {
            VerdictKind.IMPROVED,
            VerdictKind.REGRESSED,
        }:
            sections.append(
                img.add(
                    f"{stem}-power",
                    lambda t, m=m: ig.draw_power(m, t),
                    f"Power. {ig.alt_text(m)} Runs per arm needed: {m.verdict.runs_needed}.",
                )
            )
            text(
                f"The bar is the smallest change this run can detect at 80 % power (MDE "
                f"{ig.fmt_mde(m)}); the line Δ is the margin {ig.fmt_margin(m)}. "
                f"n = {m.verdict.n} → ~{m.verdict.runs_needed} units per arm to reach Δ.\n"
            )
    # Sweeps.
    for g in groups:
        if not g.swept:
            continue
        stem = _slug(g.name)
        cells_g = list(g.cells)
        varying = [k for k in g.inputs if len({m.point.get(k) for m in cells_g}) > 1]
        alt = f"{ig.humanize(g.name)} sweep. " + " ".join(
            f"{_point_label(m.point)}: {m.verdict.word} {ig.fmt_effect(m)}." for m in cells_g
        )
        moved = sum(_moved(m) for m in cells_g)
        text(f"### {ig.humanize(g.name)}: {moved} of {len(cells_g)} points moved\n")
        if len(varying) == 1 and all(
            isinstance(m.point[varying[0]], (int, float)) for m in cells_g
        ):
            key = varying[0]
            cells_g.sort(key=lambda m: m.point[key])
            xs = [float(m.point[key]) for m in cells_g]
            units = all(ig.in_units(m) for m in cells_g)
            if units:
                # The effect row is in units (a sweep is one metric): the alt gives both.
                alt = f"{ig.humanize(g.name)} sweep. " + " ".join(
                    f"{_point_label(m.point)}: {m.verdict.word} {ig.fmt_change(m)} "
                    f"({ig.fmt_effect(m)})."
                    for m in cells_g
                )
            sections.append(
                img.add(
                    f"{stem}-sweep",
                    lambda t, c=cells_g, xs=xs, k=key: ig.draw_sweep(
                        c, xs, t, x_name=k, order=order
                    ),
                    alt,
                )
            )
            text(_ci_line(cells_g, [f"`{key}`={m.point[key]:g}" for m in cells_g], units=units))
            change = (
                f"the change in {cells_g[0].units.strip()} at each point (the ratio at that "
                "point's base median), over the margin "
                if units
                else "the change at each point over the margin "
            )
            text(
                f"*Top: every run at each `{key}` point (grey base, blue candidate), lines join "
                "the medians, and a dashed line runs from the base to the candidate median; the "
                f"points sit at even steps in sweep order. Bottom: {change}"
                f"{ig.fmt_margin(cells_g[0])}. "
                f"{_order_note(cells_g, where='under the graphic', order=order)}*\n"
            )
        elif len(varying) == 2:  # noqa: PLR2004
            kx, ky = varying
            xs = sorted({m.point[kx] for m in cells_g}, key=_sort_key)
            ys = sorted({m.point[ky] for m in cells_g}, key=_sort_key)
            by = {(m.point[kx], m.point[ky]): m for m in cells_g}
            if len(by) == len(xs) * len(ys):
                grid = [[by[(x, y)] for x in xs] for y in ys]
                sections.append(
                    img.add(
                        f"{stem}-heatmap",
                        lambda t, gr=grid, xs=xs, ys=ys, kx=kx, ky=ky: ig.draw_heatmap(
                            gr, xs, ys, t, x_name=kx, y_name=ky, order=order
                        ),
                        alt,
                    )
                )
                text(
                    "*Each cell is the change at that point, rounded to a whole number: blue "
                    f"better, orange worse; hatched (?): the CI crosses {ig.fmt_margin(cells_g[0])}. "
                    f"{_order_note(cells_g, where='under the graphic', order=order)}*\n"
                )
        elif cells_g[0].kind == "positive" or all(m.kind == cells_g[0].kind for m in cells_g):
            labels = [_point_label(m.point) for m in cells_g]
            sections.append(
                img.add(
                    f"{stem}-forest",
                    lambda t, c=cells_g, lab=labels: ig.draw_forest(c, t, labels=lab, order=order),
                    alt,
                )
            )
            text(_ci_line(cells_g, labels))
            text(f"*{_forest_key(cells_g)}*\n")
        text(
            "<details><summary>Every point</summary>\n\n"
            + _design_line(cells_g, points=len(cells_g))
            + "\n\n"
            + _verdict_table(cells_g)
            + "\n</details>\n"
        )
    # Method, diagnostics, data.
    csv_path = out / "evidence-data.csv"
    csv_path.write_text(_csv(groups), encoding="utf-8")
    text(
        "<details><summary>Method, diagnostics and data</summary>\n\n"
        f"Every decision reads the 90 % CI (one-sided α = {ALPHA}) against the margin; "
        "the charts draw no interval, so each caption gives the CI. Positive metrics compare on the log scale (ratio of "
        "geometric means); binary metrics use Wilson per arm and the Newcombe difference. BCa "
        "bootstrap (10 000 resamples, fixed seed) from 10 units per arm, Welch t below that. "
        "Holm over the primary metrics (their CIs widened to α/m), Benjamini–Hochberg over the "
        "rest. n was fixed before the run; no peeking correction is applied. "
        "In each waffle the dot under the squares is the difference over the shaded margin.\n\n"
        + (_design_line(singles[:1]) + "\n\n" if singles else "")
        + _verdict_table(cells)
    )
    if diagnostics:
        for m in [x for x in singles if x.primary] or singles[:1]:
            if isinstance(m.effect, Effect):
                stem = _slug(m.name)
                sections.append(
                    img.add(
                        f"{stem}-diagnostics",
                        lambda t, m=m: ig.draw_diagnostics(m, t),
                        f"Diagnostics for {m.name}: value against run order by arm.",
                    )
                )
                shape = (
                    " the marker shape is the shard."
                    if any(c is not None for c in m.clusters)
                    else " one dot per run."
                )
                text(
                    f"`{m.name}` against run order: lines are the least-squares trend per arm;"
                    f"{shape}\n"
                )
    if skipped:
        text("Not analysed:\n\n" + "\n".join(f"- {s}" for s in skipped) + "\n")
    sections.append(lambda u: f"\nData: [{csv_path.name}]({u(csv_path.name)})\n\n</details>\n")
    files = {**img.files, csv_path.name: csv_path}
    report = Report(out, list(groups), files, sections, list(skipped), out / "evidence.md")
    report.render(url_base, svg=svg)
    return report


def _sort_key(value: object) -> tuple[int, float | str]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (1, str(value))


# --------------------------------------------------------------------------------------
# Entry points.


def report_from_rows(
    base_rows: Sequence[Mapping],
    cand_rows: Sequence[Mapping],
    out_dir: str | Path,
    *,
    primary: Sequence[str] = (),
    margin: float | None = None,
    paired: bool = False,
    url_base: UrlBase = None,
    svg: bool = True,
    order: ig.OrderMode = "auto",
) -> Report:
    """The report for two kbench row lists (*order*: see :func:`write_report`)."""
    groups, skipped = analyse_data(
        data_from_rows(base_rows, cand_rows), primary=primary, margin=margin, paired=paired
    )
    return write_report(groups, out_dir, url_base=url_base, skipped=skipped, svg=svg, order=order)


def report_from_results(
    baseline: BenchResult,
    candidate: BenchResult,
    out_dir: str | Path,
    *,
    primary: Sequence[str] = (),
    margin: float | None = None,
    paired: bool = False,
    url_base: UrlBase = None,
    svg: bool = True,
    order: ig.OrderMode = "auto",
) -> Report:
    """The report for two bencher recordings (*order*: see :func:`write_report`)."""
    groups, skipped = analyse_data(
        data_from_results(baseline, candidate), primary=primary, margin=margin, paired=paired
    )
    return write_report(groups, out_dir, url_base=url_base, skipped=skipped, svg=svg, order=order)


def main_rows(argv: Sequence[str]) -> int:
    """``bencher evidence-rows BASE.json CAND.json --report DIR [...]``."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="bencher evidence-rows",
        description="Write the statistical evidence report for two kbench row files.",
    )
    parser.add_argument("baseline", help="base row file (JSON list of rows)")
    parser.add_argument("candidate", help="candidate row file")
    parser.add_argument(
        "--report", required=True, metavar="DIR", help="write evidence.md and its images here"
    )
    add_report_options(parser)
    args = parser.parse_args(list(argv))
    for path in (args.baseline, args.candidate):
        if not Path(path).exists():
            print(f"row file not found: {path}", file=sys.stderr)  # noqa: T201 - CLI error output
            return 2
    try:
        report = report_from_rows(
            load_rows(args.baseline),
            load_rows(args.candidate),
            args.report,
            primary=split_names(args.primary),
            margin=args.margin,
            paired=args.paired,
            url_base=args.url_base,
            svg=not args.still_png,
            order=args.order,
        )
    except (ValueError, KeyError) as exc:
        print(f"evidence-rows failed: {exc}", file=sys.stderr)  # noqa: T201 - CLI error output
        return 1
    print(report.markdown_path)  # noqa: T201 - CLI prints the output path
    return 0


def split_names(text: str | None) -> list[str]:
    """``"a, b"`` -> ``["a", "b"]``."""
    return [s.strip() for s in (text or "").split(",") if s.strip()]


def add_report_options(parser: Any) -> None:
    """The analysis options ``evidence-rows`` and ``compare --report`` share."""
    parser.add_argument("--primary", metavar="M1,M2", help="the 1-3 metrics the PR claims (Holm)")
    parser.add_argument(
        "--margin",
        type=float,
        metavar="D",
        help="margin Δ for every metric: relative for positive metrics (0.05 = ±5 %%), absolute otherwise (0.05 = ±5 pp)",
    )
    parser.add_argument("--paired", action="store_true", help="pair the arms by repeat id")
    parser.add_argument(
        "--url-base", metavar="URL", help="prefix for image links (default: relative paths)"
    )
    parser.add_argument(
        "--still-png",
        dest="still_png",
        action="store_true",
        help="link the still PNGs, not the animated SVGs (for a host that does not serve SVG as an image)",
    )
    parser.add_argument(
        "--order",
        choices=ig.ORDER_MODES,
        default="auto",
        help="draw the run-order strip: auto (only when the design is not simple), always or never",
    )
