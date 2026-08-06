"""Run ONE merge strategy for issue #1113 in a fresh process; print a JSON result line.

Each strategy runs in its own process so peak-RSS numbers (VmHWM) do not
contaminate each other.  Bencher's rerun composer is loaded *without* executing
``bencher/__init__`` (which drags in panel/holoviews and would add hundreds of
MB of unrelated import RSS to the measurement) -- only
``composable_container_rerun.py`` and its two lightweight sibling modules run.

Strategies (see RESULTS.md):
- null : imports only (rerun + pyarrow + numpy) -- the process RSS floor.
- a    : today's path, ``ComposableContainerRerun.render()`` verbatim
         (decode all items -> hold all chunks -> memory sink ->
         ``drain_as_bytes`` -> ``write_bytes``).
- b    : the #1104 rider: identical decode/re-root (``_read_items``), but the
         output recording streams to disk via ``RecordingStream.save(path)``
         instead of ``memory_recording().drain_as_bytes()``.
- c    : log-at-sink: ONE host recording with a ``save()`` file sink; each
         item's data is logged directly under its final ``item_{i}`` prefix at
         collect time.  No per-item intermediate recording exists at all.
- d    : re-root-at-collect for PRE-EXISTING .rrd blobs: stream chunks with
         ``RrdReader.stream()`` (a LazyChunkStream), rewrite each chunk's
         entity path with ``with_entity_path`` (Arrow metadata rewrite), and
         forward it immediately into the ``save()``-sinked host recording.
         Nothing is accumulated.
- d2   : same re-root but entirely rust-side:
         ``LazyChunkStream.merge(*streams).write_rrd(path)``.  No blueprint
         (write_rrd emits a single recording store), included to measure the
         SDK's native streaming pipeline.  NOTE: ``merge`` executes all input
         streams CONCURRENTLY, so its footprint grows with item count.
- d2s  : sequential rust pipeline: one ``LazyChunkStream.from_iter`` over a
         Python generator that walks the items one at a time -> ``write_rrd``.
- cf/df: c and d with a blocking ``recording.flush()`` after every item, to
         test whether growth in c is un-drained batcher/sink backlog.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
import types
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

ITEM_CFG = {"steps": 500, "images": 8, "size": 512, "tensor": 64}


def vmhwm_mb() -> float:
    """Peak resident set size of this process (VmHWM), in MB."""
    with open("/proc/self/status", encoding="utf-8") as f:
        for line in f:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024.0
    raise RuntimeError("VmHWM not found in /proc/self/status")


def load_ccr():
    """Import composable_container_rerun without executing ``bencher/__init__``.

    Stub parent packages are inserted with only ``__path__`` set, so the import
    machinery finds the submodule files but never runs the package initializers
    (which import panel/holoviews and would inflate the RSS floor).
    """
    for name, sub in [
        ("bencher", "bencher"),
        ("bencher.results", "bencher/results"),
        ("bencher.results.composable_container", "bencher/results/composable_container"),
    ]:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(REPO / Path(*sub.split("/")))]
            sys.modules[name] = mod
    import bencher.results.composable_container.composable_container_rerun as ccr

    return ccr


def _compose_type():
    from bencher.results.composable_container.composable_container_base import ComposeType

    return ComposeType


def strat_null(_paths, _out, _n_items) -> None:
    import numpy  # noqa: F401
    import pyarrow  # noqa: F401
    import rerun
    import rerun.blueprint  # noqa: F401


def strat_a(paths, out, _n_items) -> None:
    """Today's path, using the real bencher class end to end."""
    ccr = load_ccr()
    compose_type = _compose_type()
    cc = ccr.ComposableContainerRerun(compose_method=compose_type.right, output_path=str(out))
    for p in paths:
        cc.append(str(p))
    cc.render()


def _finish(recording, cc, rrb, items_meta) -> None:
    """Send the same blueprint render() builds, then flush the sink."""
    blueprint = rrb.Blueprint(
        cc._layout(rrb, items_meta),
        auto_layout=False,
        auto_views=False,
        collapse_panels=True,
    )
    recording.send_blueprint(blueprint, make_active=True, make_default=True)
    recording.flush()
    recording.disconnect()


def strat_b(paths, out, _n_items) -> None:
    """#1104 rider: same decode/hold-all merge, but ``save()`` replaces drain."""
    import rerun as rr
    import rerun.blueprint as rrb

    ccr = load_ccr()
    compose_type = _compose_type()
    cc = ccr.ComposableContainerRerun(compose_method=compose_type.right, output_path=str(out))
    for p in paths:
        cc.append(str(p))
    items = cc._read_items()  # identical decode + with_entity_path re-root as render()
    recording = rr.RecordingStream(cc.application_id, make_default=False, make_thread_default=False)
    recording.save(str(out))  # streaming file sink -- the only change vs strategy a
    for item in items:
        recording.send_chunks(item.chunks)
    _finish(recording, cc, rrb, items)


def strat_c(_paths, out, n_items, *, flush_per_item: bool = False) -> None:
    """Log-at-sink: one host recording, items logged straight under their prefix."""
    import rerun as rr
    import rerun.blueprint as rrb
    from itemgen import log_item

    ccr = load_ccr()
    compose_type = _compose_type()
    recording = rr.RecordingStream(
        "bencher/composed", make_default=False, make_thread_default=False
    )
    recording.save(str(out))
    kinds = {
        ccr.RerunViewKind.spatial_2d,
        ccr.RerunViewKind.time_series,
        ccr.RerunViewKind.tensor,
    }
    items_meta = []
    for i in range(n_items):
        log_item(recording, f"item_{i}", i, **ITEM_CFG)
        recording.reset_time()
        if flush_per_item:
            recording.flush()
        items_meta.append(
            ccr._ComposedItem(prefix=f"/item_{i}", label=f"Item {i + 1}", view_kinds=set(kinds))
        )
    cc = ccr.ComposableContainerRerun(compose_method=compose_type.right)
    _finish(recording, cc, rrb, items_meta)


def strat_cf(paths, out, n_items) -> None:
    """Strategy c with a blocking flush after every item (bounds sink backlog)."""
    strat_c(paths, out, n_items, flush_per_item=True)


def strat_d(paths, out, _n_items, *, flush_per_item: bool = False) -> None:
    """Re-root-at-collect, streaming: chunk in -> metadata rewrite -> chunk out."""
    import rerun as rr
    import rerun.blueprint as rrb
    from rerun.experimental import RrdReader

    ccr = load_ccr()
    compose_type = _compose_type()
    recording = rr.RecordingStream(
        "bencher/composed", make_default=False, make_thread_default=False
    )
    recording.save(str(out))
    items_meta = []
    for index, path in enumerate(paths):
        prefix = f"/item_{index}"
        kinds: set = set()
        reader = RrdReader(path)
        for store in reader.recordings():
            for chunk in reader.stream(store=store):
                source = str(chunk.entity_path).lstrip("/")
                rerooted = chunk.with_entity_path(f"{prefix}/{source}")
                kinds |= ccr._batch_view_kinds(rerooted.to_record_batch())
                recording.send_chunks([rerooted])  # forwarded immediately, never retained
        if flush_per_item:
            recording.flush()
        items_meta.append(
            ccr._ComposedItem(prefix=prefix, label=f"Item {index + 1}", view_kinds=kinds)
        )
    cc = ccr.ComposableContainerRerun(compose_method=compose_type.right)
    _finish(recording, cc, rrb, items_meta)


def strat_df(paths, out, n_items) -> None:
    """Strategy d with a blocking flush after every item (bounds sink backlog)."""
    strat_d(paths, out, n_items, flush_per_item=True)


def strat_d2(paths, out, _n_items) -> None:
    """Rust-side streaming pipeline: RrdReader.stream -> map(re-root) -> merge -> write_rrd."""
    from rerun.experimental import LazyChunkStream, RrdReader

    streams = []
    for index, path in enumerate(paths):
        prefix = f"/item_{index}"

        def reroot(chunk, prefix=prefix):
            return chunk.with_entity_path(f"{prefix}/{str(chunk.entity_path).lstrip('/')}")

        streams.append(RrdReader(path).stream().map(reroot))
    LazyChunkStream.merge(*streams).write_rrd(
        str(out), application_id="bencher/composed", recording_id=str(uuid.uuid4())
    )


def strat_d2s(paths, out, _n_items) -> None:
    """Sequential rust pipeline: one from_iter generator over all items -> write_rrd."""
    from rerun.experimental import LazyChunkStream, RrdReader

    def rerooted_chunks():
        for index, path in enumerate(paths):
            prefix = f"/item_{index}"
            reader = RrdReader(path)
            for store in reader.recordings():
                for chunk in reader.stream(store=store):
                    yield chunk.with_entity_path(f"{prefix}/{str(chunk.entity_path).lstrip('/')}")

    LazyChunkStream.from_iter(rerooted_chunks()).write_rrd(
        str(out), application_id="bencher/composed", recording_id=str(uuid.uuid4())
    )


STRATEGIES = {
    "null": strat_null,
    "a": strat_a,
    "b": strat_b,
    "c": strat_c,
    "cf": strat_cf,
    "d": strat_d,
    "df": strat_df,
    "d2": strat_d2,
    "d2s": strat_d2s,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("strategy", choices=sorted(STRATEGIES))
    parser.add_argument("--items-dir", type=Path, help="directory of pre-generated item .rrd")
    parser.add_argument("--out", type=Path, help="output .rrd path")
    parser.add_argument("--n-items", type=int, default=0, help="item count (strategy c)")
    args = parser.parse_args()

    paths = sorted(args.items_dir.glob("item_*.rrd")) if args.items_dir else []
    input_bytes = sum(p.stat().st_size for p in paths)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.unlink(missing_ok=True)

    start = time.perf_counter()
    STRATEGIES[args.strategy](paths, args.out, args.n_items)
    wall = time.perf_counter() - start

    print(
        json.dumps(
            {
                "strategy": args.strategy,
                "n_items": args.n_items or len(paths),
                "input_mb": round(input_bytes / 2**20, 1),
                "out_mb": round(args.out.stat().st_size / 2**20, 1)
                if args.out and args.out.is_file()
                else 0.0,
                "wall_s": round(wall, 2),
                "vmhwm_mb": round(vmhwm_mb(), 1),
                "ru_maxrss_mb": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1
                ),
                "pid": os.getpid(),
            }
        )
    )


if __name__ == "__main__":
    main()
