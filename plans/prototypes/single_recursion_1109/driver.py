"""Driver for the issue #1109 prototype: exercises the ONE recursion over the three
input shapes the three existing builders own today, saves real .rrd files, and
verifies both the recording contents and the blueprint structure programmatically.

Run:  pixi run python plans/prototypes/single_recursion_1109/driver.py

(a) a small real sweep dataset (rerun_result's input: a dataset of VALUES)
(b) a grid of pre-existing .rrd blobs (rerun_summary's input: a dataset of PATHS)
(c) a flat list of .rrd paths (ComposableContainerRerun's input)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).parent))

from single_recursion import (  # noqa: E402
    Channel,
    channel_of_compose_type,
    default_facet_channels,
    from_blob_dataset,
    from_flat_list,
    from_sweep_dataset,
    pane_layout_channels,
    realize,
)

OUT = Path(__file__).parent / "out"


# ---------------------------------------------------------------------------
# Verification: read a saved .rrd back and extract hard facts
# ---------------------------------------------------------------------------


def rrd_facts(path: Path) -> tuple[set[str], set[str], dict[str, int]]:
    """(entity paths, timeline names, per-timeline max raw value) of a saved .rrd."""
    from rerun.experimental import RrdReader

    import pyarrow as pa

    reader = RrdReader(str(path))
    if not reader.blueprints():
        raise AssertionError(f"saved file carries no blueprint store: {path}")
    entities: set[str] = set()
    timelines: set[str] = set()
    timeline_max: dict[str, int] = {}
    for store in reader.recordings():
        for chunk in reader.stream(store=store):
            # FINDING: rerun's unescaped path charset is [A-Za-z0-9_.-]; a literal '='
            # in a path part is legal but the SDK renders it backslash-escaped in the
            # string form ('algo\=fast'). Normalized here; the part itself holds '='.
            entities.add(str(chunk.entity_path).replace("\\", ""))
            batch = chunk.to_record_batch()
            for arrow_field in batch.schema:
                if (arrow_field.metadata or {}).get(b"rerun:kind") != b"index":
                    continue
                timelines.add(arrow_field.name)
                column = batch.column(batch.schema.get_field_index(arrow_field.name))
                values = column.cast(pa.int64()).to_numpy(zero_copy_only=False)
                if len(values):
                    current = timeline_max.get(arrow_field.name, np.iinfo(np.int64).min)
                    timeline_max[arrow_field.name] = max(current, int(values.max()))
    return entities, timelines, timeline_max


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def count_rrds(directory: Path) -> int:
    return len(list(directory.rglob("*.rrd"))) if directory.exists() else 0


# ---------------------------------------------------------------------------
# (a) A small real sweep dataset -> native views
# ---------------------------------------------------------------------------


import bencher as bch  # noqa: E402


class SweepCfg(bch.ParametrizedSweep):
    theta = bch.FloatSweep(bounds=[0, math.pi], samples=6, units="rad")
    freq = bch.FloatSweep(bounds=[1.0, 3.0], samples=3)
    algo = bch.StringSweep(["fast", "slow"])
    out_sin = bch.ResultFloat(units="v")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        gain = 1.0 if self.algo == "fast" else 0.5
        self.out_sin = gain * math.sin(self.freq * self.theta)
        return self.get_results_values_as_dict()


def scenario_a() -> None:
    print("\n(a) real sweep dataset -> DatasetLeaf tree (replaces rerun_result recursions)")
    from bencher.results.bench_result_base import ReduceType

    bench = SweepCfg().to_bench(bch.BenchRunCfg(auto_plot=False))
    res = bench.plot_sweep("proto_1109_sweep")
    dataset = res.to_dataset(reduce=ReduceType.SQUEEZE)
    float_dims = [v.name for v in res.plt_cnt_cfg.float_vars if v.name in dataset.dims]
    cat_dims = [v.name for v in res.plt_cnt_cfg.cat_vars if v.name in dataset.dims]

    # `freq` assigned to the TIME channel: the generalized over_time, on its OWN named
    # timeline; `theta` is the leaf X, ALSO a named timeline. Two time-like dims that
    # today would collide on log_tick coexist here.
    node = from_sweep_dataset(
        dataset,
        result_vars=list(res.bench_cfg.result_vars),
        float_dims=float_dims,
        cat_dims=cat_dims,
        time_channel_dims=("freq",),
    )
    path, lowered = realize(node, application_id="proto_a", output_path=OUT / "a_sweep.rrd")
    print(f"  sketch: {lowered.sketch}")
    entities, timelines, _ = rrd_facts(path)

    check("saved .rrd exists and reopens", path.is_file() and bool(entities), str(path))
    check(
        "entity paths are dim=value trees, no /item_N",
        "/algo=fast/out_sin" in entities and "/algo=slow/out_sin" in entities,
        f"entities={sorted(e for e in entities if 'algo' in e)}",
    )
    check(
        "named timelines per Time-like dim; log_tick dead",
        "theta" in timelines and "freq" in timelines and "log_tick" not in timelines,
        f"timelines={sorted(timelines)}",
    )
    check(
        "blueprint: TIME peels to a shared structure, cats to Horizontal, leaf lines",
        lowered.sketch.startswith("Time[freq]x3(Horizontal[")
        and "Line[out_sin/theta]" in lowered.sketch,
        lowered.sketch,
    )


# ---------------------------------------------------------------------------
# (b) a dataset of pre-existing .rrd blob paths -> merged store, ZERO intermediates
# ---------------------------------------------------------------------------


def make_blob(path: Path, entity: str, values: list[float]) -> Path:
    import rerun as rr

    rec = rr.RecordingStream(
        f"proto/blob/{path.stem}", make_default=False, make_thread_default=False
    )
    rec.save(str(path))
    for step, value in enumerate(values):
        rec.set_time("step", sequence=step)
        rec.log(entity, rr.Scalars(value))
    rec.flush()
    return path


def make_blob_grid() -> list[Path]:
    blob_dir = OUT / "blobs"
    blob_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(6):
        values = [math.sin(0.5 * i + 0.3 * s) for s in range(5)]
        paths.append(make_blob(blob_dir / f"blob_{i}.rrd", "signal", values))
    return paths


def scenario_b(blob_paths: list[Path]) -> None:
    print("\n(b) dataset of .rrd blob paths -> BlobLeaf tree (replaces rerun_summary._compose_ds)")
    import param

    from bencher.variables.results import ResultRerun

    class Holder(param.Parameterized):
        rec = ResultRerun()

    rv = Holder.param.rec

    grid = np.array([str(p) for p in blob_paths], dtype=object).reshape(2, 3)
    dataset = xr.Dataset(
        {"rec": (("alpha", "beta"), grid)},
        coords={"alpha": ["a0", "a1"], "beta": [0.5, 1.5, 2.5]},
    )

    from bencher.utils import gen_rerun_data_path

    cache_rrd_dir = Path(gen_rerun_data_path("probe")).parent  # where _compose_ds writes
    before = count_rrds(cache_rrd_dir)

    node = from_blob_dataset(dataset, rv)  # default channels: alternate row/col
    path, lowered = realize(node, application_id="proto_b", output_path=OUT / "b_grid.rrd")
    print(f"  sketch: {lowered.sketch}")

    after = count_rrds(cache_rrd_dir)
    entities, timelines, _ = rrd_facts(path)

    check(
        "zero per-level intermediate .rrd files (one host recording, one drain)",
        after == before,
        f"cache rrd count before={before} after={after}",
    )
    check(
        "entity paths derive from dim names + values, not /item_N",
        "/beta=0.5/alpha=a0/signal" in entities and "/beta=2.5/alpha=a1/signal" in entities,
        f"entities={sorted(entities)[:4]}...",
    )
    check(
        "blueprint: Vertical of Horizontals mirroring the peel",
        lowered.sketch.startswith("Vertical[proto_b](Horizontal[beta=0.5]"),
        lowered.sketch,
    )
    check("blob timelines survive the merge", "step" in timelines, f"timelines={sorted(timelines)}")


# ---------------------------------------------------------------------------
# (c) a flat list of .rrd paths -> one Compose level (replaces ComposableContainerRerun)
# ---------------------------------------------------------------------------


def scenario_c(blob_paths: list[Path]) -> None:
    print("\n(c) flat list of .rrd paths (replaces ComposableContainerRerun._layout/_read_item)")
    import rerun.blueprint as rrb

    three = blob_paths[:3]
    labels = ["run one", "run two", "run three"]

    # legacy ComposeType through the shim: "right" -> FACET_COL -> Horizontal
    node = from_flat_list(three, along="right", labels=labels)
    path, lowered = realize(node, application_id="proto_c_row", output_path=OUT / "c_row.rrd")
    print(f"  sketch(right): {lowered.sketch}")
    entities, _, _ = rrd_facts(path)
    check(
        "ComposeType.right shims to FACET_COL -> rrb.Horizontal",
        isinstance(lowered.view, rrb.Horizontal) and "/run_one/signal" in entities,
        lowered.sketch,
    )

    # TABS: expressible for the first time (absent from ComposeType entirely)
    node = from_flat_list(three, along=Channel.TABS, labels=labels)
    _, lowered = realize(node, application_id="proto_c_tabs", output_path=OUT / "c_tabs.rrd")
    print(f"  sketch(tabs):  {lowered.sketch}")
    check(
        "TABS lowers to rrb.Tabs (inexpressible via ComposeType)",
        isinstance(lowered.view, rrb.Tabs),
    )

    # OVERLAY: sibling entity paths, one shared view
    node = from_flat_list(three, along=Channel.OVERLAY, labels=labels)
    path, lowered = realize(
        node, application_id="proto_c_overlay", output_path=OUT / "c_overlay.rrd"
    )
    print(f"  sketch(overlay): {lowered.sketch}")
    entities, _, _ = rrd_facts(path)
    check(
        "OVERLAY: siblings in one shared view at the parent origin",
        isinstance(lowered.view, rrb.TimeSeriesView)
        and {"/run_one/signal", "/run_two/signal", "/run_three/signal"} <= entities,
        lowered.sketch,
    )

    # TIME over blobs: temporal splice on the items' own timelines (legacy `sequence`)
    node = from_flat_list(three, along="sequence", labels=labels)
    path, lowered = realize(node, application_id="proto_c_seq", output_path=OUT / "c_seq.rrd")
    print(f"  sketch(sequence): {lowered.sketch}")
    _, timelines, timeline_max = rrd_facts(path)
    # 3 blobs x steps 0..4, gap 1 between: expected final step index 14
    check(
        "sequence shims to TIME; blobs splice end-to-end on their own timeline",
        timeline_max.get("step") == 14,
        f"step max={timeline_max.get('step')} (expected 14), timelines={sorted(timelines)}",
    )

    # SPREAD: routed through the grammar's documented substitution chain -> OVERLAY
    node = from_flat_list(three, along=Channel.SPREAD, labels=labels)
    _, lowered = realize(node, application_id="proto_c_spread", output_path=OUT / "c_spread.rrd")
    print(f"  sketch(spread): {lowered.sketch}")
    check(
        "SPREAD walks substitute(): spread->overlay, visibly recorded",
        lowered.sketch.startswith("Subst[spread->overlay]"),
        lowered.sketch,
    )


# ---------------------------------------------------------------------------
# Vocabulary collapse tables (printed as evidence)
# ---------------------------------------------------------------------------


def print_tables() -> None:
    from bencher.results.composable_container.composable_container_base import (
        ComposeType,
        PaneLayout,
    )

    print("\nComposeType -> Channel (total):")
    for member in ComposeType:
        print(f"  ComposeType.{member.name:<9} -> Channel.{channel_of_compose_type(member).name}")
    print(
        "PaneLayout -> per-level Channel assignment over 3 facet levels (a POLICY, not a channel):"
    )
    for member in PaneLayout:
        chans = ", ".join(c.name for c in pane_layout_channels(member, 3))
        print(f"  PaneLayout.{member.name:<13} -> [{chans}]")
    chans = ", ".join(c.name for c in default_facet_channels(4))
    print(f"default_facet_channels(4) (replaces compose_method_list_for_dims): [{chans}]")
    chans = ", ".join(c.name for c in default_facet_channels(3, time_levels=-1))
    print(f"default_facet_channels(3, time_levels=-1) (old time_sequence_dimension=-1): [{chans}]")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print_tables()
    scenario_a()
    blob_paths = make_blob_grid()
    scenario_b(blob_paths)
    scenario_c(blob_paths)
    print("\nAll scenarios passed. Outputs in", OUT)


if __name__ == "__main__":
    main()
