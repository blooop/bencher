"""Prototype for issue #1109: the single recursion that replaces the three rerun
blueprint builders.

THROWAWAY PROTOTYPE — evidence for the issue, not production integration. It does not
modify any existing bencher module; it *imports* the grammar (`bencher.grammar`) as its
input language and reuses the proven chunk-merge helpers from
`composable_container_rerun` as leaf machinery.

The one recursion
-----------------

    lower(node: Node, sink: RerunSink, name: str) -> Lowered

where

    Node  = Compose            # items laid out along one Channel (bencher.grammar)
          | DatasetLeaf        # xarray values to log natively (rerun_result's input)
          | BlobLeaf           # an existing .rrd to splice in (summary/container input)
    Lowered = (blueprint view, view kinds seen, structural sketch)

`Compose.items` are `Slot(key, node, coord)` — the key is the human path segment
("theta=0.5"), the coord the numeric coordinate for TIME lowering. Bare items are
auto-keyed by index (the flat-list case).

Channel -> rerun lowering (A6 §3 parity table, made executable):

    FACET_ROW -> rrb.Vertical        FACET_COL -> rrb.Horizontal      TABS -> rrb.Tabs
    OVERLAY   -> sibling entity paths, ONE shared view at the parent origin
    TIME      -> a named timeline per Time dim (dataset leaves), or temporal splice
                 on the items' own timelines (blob leaves — see finding in driver)
    SPREAD    -> routed through grammar.substitute() (documented chain: SPREAD->OVERLAY)
    X/Y/Z     -> within-leaf channels; illegal as a Compose layout channel

The host owns the recording (issue #1104 ruling): `realize()` creates one
RecordingStream, streams it straight to disk (`RecordingStream.save`, no
`drain_as_bytes` spike), hands the recursion a prefix-scoped `RerunSink`, and sends one
Blueprint at the end. There are NO per-recursion-level intermediate .rrd files.
"""

from __future__ import annotations

import logging
import re as _re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Union

import numpy as np
import xarray as xr

from bencher.grammar import RERUN_CAPABILITIES, Channel, Compose, Direct, Substituted, substitute
from bencher.results.composable_container.composable_container_base import (
    ComposeType,
    PaneLayout,
)

# Reused, unchanged, as *leaf machinery*: the chunk-level merge engine survives; what
# dies is the per-level render-to-.rrd recursion wrapped around it.
from bencher.results.composable_container.composable_container_rerun import (
    _SPLICE_GAP_NS,
    _VIEW_CLASS_NAMES,
    _VIEW_NAMES,
    RerunViewKind,
    _read_item,
    _set_recording_time,
    _splice_offsets,
    _shifted_chunks,
)
from bencher.variables.results import result_is_missing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The leaf sum type + Slot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetLeaf:
    """Values to log natively — rerun_result's input shape. <=3 residual dims."""

    dataset: xr.Dataset
    result_var: object  # a bencher result Parameter (has .name); used by result_is_missing


@dataclass(frozen=True)
class BlobLeaf:
    """An existing .rrd recording to splice into the shared store — the
    rerun_summary / ComposableContainerRerun input shape."""

    path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))


Node = Union[Compose, DatasetLeaf, BlobLeaf]


@dataclass(frozen=True)
class Slot:
    """One keyed item inside a Compose.

    key   -> the human-navigable path segment AND the tab/view name ("theta=0.5").
    coord -> the numeric coordinate when the parent composes along TIME.

    FINDING: the grammar's `Compose.items: tuple[object, ...]` is not enough for
    lowering — every layout channel needs a per-item *name* (tab title, view name,
    entity-path segment) and TIME additionally needs a per-item *coordinate*. The
    planner producer gets these for free from the dim it slices; the user producer
    needs defaults (index keys). Slot is where that fact lives in this prototype.
    """

    key: str
    node: Node
    coord: float | int | None = None


def _seg(key: str) -> str:
    """Sanitize a slot key into one entity-path segment.

    Measured on rerun-sdk 0.35: the unescaped path charset is [A-Za-z0-9_.-];
    whitespace triggers a parse warning and backslash-escaping, and '=' is accepted
    but rendered escaped ('algo\\=fast') in path string forms. '=' is kept for
    human-navigable `dim=value` segments; whitespace and separators are folded to '_'.
    """
    return _re.sub(r"\s+", "_", key.replace("/", "_").replace("\\", "_").strip())


def _timeline_name(slots: list[Slot], fallback: str) -> str:
    """Timeline for a TIME compose: the peeled dim's name, recovered from 'dim=value'
    keys (convention). FINDING: this is the concrete place where Compose needs the
    peeled dim's name carried explicitly rather than parsed back out of labels."""
    names = {s.key.split("=", 1)[0] for s in slots if "=" in s.key}
    if len(names) == 1:
        return next(iter(names))
    return fallback


# ---------------------------------------------------------------------------
# The prefix-scoped sink (issue #1104 §3, prototyped)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RerunSink:
    """A prefix- and time-scoped writer into the single host-owned recording.

    The host assigns the prefix — plugins/recursion levels never invent global entity
    paths, which is what makes `/item_N` re-rooting and missing-file re-checks
    unrepresentable.
    """

    recording: object
    prefix: str = ""
    times: tuple[tuple[str, float | int], ...] = ()

    def scoped(self, segment: str) -> RerunSink:
        return replace(self, prefix=f"{self.prefix}/{_seg(segment)}")

    def at(self, timeline: str, value: float | int) -> RerunSink:
        """Return a sink whose every log is stamped onto `timeline` at `value`."""
        return replace(self, times=(*self.times, (timeline, value)))

    def path(self, sub_path: str) -> str:
        return f"{self.prefix}/{sub_path}" if sub_path else self.prefix or "/"

    def log(self, sub_path: str, *archetypes) -> None:
        self.recording.reset_time()
        for timeline, value in self.times:
            _set_named_time(self.recording, timeline, value)
        self.recording.log(self.path(sub_path), *archetypes)

    def send_chunks(self, chunks) -> None:
        self.recording.send_chunks(chunks)


def _set_named_time(recording, timeline: str, value: float | int) -> None:
    """Named timelines: int coords -> sequence index, float coords -> duration secs."""
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        recording.set_time(timeline, sequence=int(value))
    else:
        recording.set_time(timeline, duration=float(value))


# ---------------------------------------------------------------------------
# Lowered: what one recursion level returns
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Lowered:
    view: object  # an rrb view/container node
    kinds: frozenset  # RerunViewKind union of the subtree (drives shared-view choice)
    sketch: str  # structural summary, asserted on programmatically by the driver


def _view_stack(rrb, kinds, *, origin: str, label: str) -> object:
    """One view (or a vertical stack) able to display every kind at `origin`.
    Same policy as ComposableContainerRerun._views."""
    ordered = [k for k in RerunViewKind if k in set(kinds)] or [RerunViewKind.spatial_2d]
    views = [
        getattr(rrb, _VIEW_CLASS_NAMES[k])(
            origin=origin,
            name=label if len(ordered) == 1 else f"{label} — {_VIEW_NAMES[k]}",
        )
        for k in ordered
    ]
    if len(views) == 1:
        return views[0]
    return rrb.Vertical(*views, name=label)


# ---------------------------------------------------------------------------
# THE single recursion
# ---------------------------------------------------------------------------

_LAYOUT_CONTAINER = {
    Channel.FACET_ROW: "Vertical",
    Channel.FACET_COL: "Horizontal",
    Channel.TABS: "Tabs",
}


def lower(node: Node, sink: RerunSink, name: str = "root") -> Lowered:
    """Peel `Compose.along` channels over a sum-typed leaf, logging data through the
    prefix-scoped sink (effect) and returning the Blueprint node (value)."""
    import rerun.blueprint as rrb

    if isinstance(node, DatasetLeaf):
        return _lower_dataset_leaf(rrb, node, sink)
    if isinstance(node, BlobLeaf):
        return _lower_blob_leaf(rrb, node, sink, name)
    if isinstance(node, Compose):
        slots = [
            item if isinstance(item, Slot) else Slot(key=str(i), node=item, coord=i)
            for i, item in enumerate(node.items)
        ]
        return _lower_compose(rrb, slots, Channel(node.along), sink, name)
    raise TypeError(f"not a Node: {type(node).__name__}")


def _lower_compose(rrb, slots: list[Slot], along: Channel, sink: RerunSink, name: str) -> Lowered:
    if along in (Channel.X, Channel.Y, Channel.Z):
        raise ValueError(
            f"{along} is a within-leaf channel; a planner assigns it inside a DatasetLeaf, "
            "never as a Compose layout channel"
        )

    # Not directly supported as a layout channel here? Walk the documented chain.
    if along is Channel.SPREAD:
        lowering = substitute(RERUN_CAPABILITIES, along)
        if isinstance(lowering, (Direct, Substituted)):
            landed = lowering.channel if isinstance(lowering, Direct) else lowering.via[-1]
            child = _lower_compose(rrb, slots, landed, sink, name)
            walk = "->".join(lowering.via) if isinstance(lowering, Substituted) else str(landed)
            return replace(child, sketch=f"Subst[{walk}]({child.sketch})")
        raise ValueError(f"no rerun lowering for {along}: {lowering.reason}")

    if along in _LAYOUT_CONTAINER:
        children = [lower(s.node, sink.scoped(s.key), name=s.key) for s in slots]
        cls_name = _LAYOUT_CONTAINER[along]
        view = getattr(rrb, cls_name)(*[c.view for c in children], name=name)
        kinds = frozenset().union(*(c.kinds for c in children))
        sketch = f"{cls_name}[{name}](" + ", ".join(c.sketch for c in children) + ")"
        return Lowered(view=view, kinds=kinds, sketch=sketch)

    if along is Channel.OVERLAY:
        # Sibling entity paths, ONE shared view at the parent origin (A6 §3: native).
        children = [lower(s.node, sink.scoped(s.key), name=s.key) for s in slots]
        kinds = frozenset().union(*(c.kinds for c in children))
        view = _view_stack(rrb, kinds, origin=sink.prefix or "/", label=name)
        sketch = f"Overlay[{name}](" + ", ".join(_seg(s.key) for s in slots) + ")"
        return Lowered(view=view, kinds=kinds, sketch=sketch)

    if along is Channel.TIME:
        if _subtree_has_blobs(slots):
            return _lower_time_splice(rrb, slots, sink, name)
        return _lower_time_named(rrb, slots, sink, name)

    raise AssertionError(f"unhandled channel {along}")  # pragma: no cover


def _subtree_has_blobs(slots: list[Slot]) -> bool:
    for s in slots:
        node = s.node
        if isinstance(node, BlobLeaf):
            return True
        if isinstance(node, Compose):
            inner = [i if isinstance(i, Slot) else Slot("", i) for i in node.items]
            if _subtree_has_blobs(inner):
                return True
    return False


def _lower_time_named(rrb, slots: list[Slot], sink: RerunSink, name: str) -> Lowered:
    """TIME over dataset leaves: ONE named timeline per Time dim. Children share
    entity paths, distinguished only by the timeline value — this is what kills the
    'over_time and a float sweep compete for log_tick' collision (A6 §3)."""
    timeline = _timeline_name(slots, fallback=name)
    children = []
    for i, s in enumerate(slots):
        coord = s.coord if s.coord is not None else i
        children.append(lower(s.node, sink.at(timeline, coord), name=name))
    kinds = frozenset().union(*(c.kinds for c in children))
    # Identical structure at every tick: the first child's view IS the view.
    sketch = f"Time[{timeline}]x{len(children)}({children[0].sketch})"
    return Lowered(view=children[0].view, kinds=kinds, sketch=sketch)


def _flatten_blobs(
    slots: list[Slot], segments: tuple[str, ...]
) -> list[tuple[tuple[str, ...], BlobLeaf]]:
    out = []
    for s in slots:
        segs = (*segments, _seg(s.key))
        if isinstance(s.node, BlobLeaf):
            out.append((segs, s.node))
        elif isinstance(s.node, Compose):
            inner = [
                i if isinstance(i, Slot) else Slot(str(j), i) for j, i in enumerate(s.node.items)
            ]
            out.extend(_flatten_blobs(inner, segs))
        else:
            raise ValueError("TIME splice over a mixed subtree is out of prototype scope")
    return out


def _lower_time_splice(rrb, slots: list[Slot], sink: RerunSink, name: str) -> Lowered:
    """TIME over blobs: temporal splice on the items' own timelines, one shared view.

    FINDING: composing *foreign recordings* in time cannot use an outer named timeline
    without injecting a new index column into every chunk (possible with pyarrow,
    deferred); the proven splice-and-clear mechanism from ComposableContainerRerun
    lifts into the one recursion unchanged. Approx, not Native — an honest capability
    distinction between DatasetLeaf and BlobLeaf under TIME.
    """
    import rerun as rr

    flat = _flatten_blobs(slots, ())
    items = [
        _read_item(blob.path, prefix=f"{sink.prefix}/{'/'.join(segs)}", label=" ".join(segs))
        for segs, blob in flat
    ]
    offsets = _splice_offsets(items)
    for index, (item, item_offsets) in enumerate(zip(items, offsets)):
        for chunk in item.chunks:
            sink.send_chunks(_shifted_chunks(chunk, item_offsets))
        if index == len(items) - 1 or not item.time_bounds:
            continue
        for timeline, (_, last) in item.time_bounds.items():
            _set_recording_time(
                sink.recording,
                timeline,
                item.time_types[timeline],
                last + item_offsets.get(timeline, 0) + _SPLICE_GAP_NS,
            )
        sink.recording.log(item.prefix, rr.Clear(recursive=True))
        sink.recording.reset_time()
    kinds = frozenset().union(*(item.view_kinds for item in items))
    view = _view_stack(rrb, kinds, origin=sink.prefix or "/", label=name)
    sketch = f"TimeSplice[{name}]x{len(items)}"
    return Lowered(view=view, kinds=kinds, sketch=sketch)


# ---------------------------------------------------------------------------
# Leaf lowerings
# ---------------------------------------------------------------------------


def _lower_blob_leaf(rrb, leaf: BlobLeaf, sink: RerunSink, name: str) -> Lowered:
    """Splice one existing .rrd under the sink's prefix — subsumes _read_item +
    per-item view building, with the host-assigned prefix replacing /item_N."""
    item = _read_item(leaf.path, prefix=sink.prefix, label=name)
    sink.send_chunks(item.chunks)
    view = _view_stack(rrb, item.view_kinds, origin=sink.prefix or "/", label=name)
    kind_names = ",".join(sorted(k.name for k in item.view_kinds))
    return Lowered(view=view, kinds=frozenset(item.view_kinds), sketch=f"Blob[{kind_names}]")


def _is_cat(dataset: xr.Dataset, dim: str) -> bool:
    return dataset.coords[dim].dtype.kind in ("O", "U", "S", "b")


def _lower_dataset_leaf(rrb, leaf: DatasetLeaf, sink: RerunSink) -> Lowered:
    """Residual-shape mark deduction — subsumes _make_leaf_view + _log_line_graph /
    _log_bar_chart / _log_tensor / _log_result_var, in ONE pass: the same code that
    logs the data returns the view, so the two hand-synced recursions of
    rerun_result.py cannot drift."""
    import rerun as rr

    rv = leaf.result_var
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    ds = leaf.dataset
    dims = [d for d in ds[rv_name].dims]

    if len(dims) == 0:
        val = ds[rv_name].values.item()
        if not result_is_missing(rv, val):
            if isinstance(val, str):
                sink.log(rv_name, rr.TextDocument(val))
                kind = RerunViewKind.text_document
            else:
                sink.log(rv_name, rr.Scalars(float(val)))
                kind = RerunViewKind.time_series
        else:
            kind = RerunViewKind.time_series
        view = _view_stack(rrb, {kind}, origin=sink.path(rv_name), label=rv_name)
        return Lowered(view=view, kinds=frozenset({kind}), sketch=f"Scalar[{rv_name}]")

    if len(dims) == 1 and _is_cat(ds, dims[0]):
        dim = dims[0]
        values = [
            float("nan") if result_is_missing(rv, v) else float(v)
            for v in (ds[rv_name].sel({dim: c}).values.item() for c in ds.coords[dim].values)
        ]
        sink.log(rv_name, rr.BarChart(values))
        view = rrb.BarChartView(origin=sink.path(rv_name), name=rv_name)
        kinds = frozenset({RerunViewKind.bar_chart})
        return Lowered(view=view, kinds=kinds, sketch=f"Bar[{rv_name}/{dim}]")

    if len(dims) == 1:
        # 1 float dim -> a line on a timeline NAMED AFTER THE DIM (not log_tick).
        dim = dims[0]
        for coord in ds.coords[dim].values:
            val = ds[rv_name].sel({dim: coord}).values.item()
            if result_is_missing(rv, val):
                continue  # genuine gap, never fabricated (plan 23 C12)
            sink.at(dim, float(coord)).log(rv_name, rr.Scalars(float(val)))
        view = rrb.TimeSeriesView(origin=sink.path(rv_name), name=rv_name)
        kinds = frozenset({RerunViewKind.time_series})
        return Lowered(view=view, kinds=kinds, sketch=f"Line[{rv_name}/{dim}]")

    # 2-3 dims -> Tensor (heatmap / volume), same missing-cell policy as _log_tensor.
    raw = ds[rv_name].transpose(*dims).values
    arr = np.array(
        [float("nan") if result_is_missing(rv, v) else v for v in raw.ravel()],
        dtype=np.float32,
    ).reshape(raw.shape)
    finite = arr[np.isfinite(arr)]
    if finite.size:
        vmin, vmax = float(finite.min()), float(finite.max())
        if vmin == vmax:
            vmax = vmin + 1.0
        sink.log(rv_name, rr.Tensor(arr, dim_names=dims, value_range=[vmin, vmax]))
    view = rrb.TensorView(origin=sink.path(rv_name), name=rv_name)
    kinds = frozenset({RerunViewKind.tensor})
    return Lowered(view=view, kinds=kinds, sketch=f"Tensor[{rv_name}/{'x'.join(dims)}]")


# ---------------------------------------------------------------------------
# The host: one recording, one drain
# ---------------------------------------------------------------------------


def realize(root: Node, *, application_id: str, output_path: str | Path) -> tuple[Path, Lowered]:
    """RerunHost embryo: owns the recording and the namespace root, streams to disk
    (no drain_as_bytes RSS spike), sends ONE blueprint. Zero intermediate .rrd files
    regardless of recursion depth — the structural fix over rerun_summary._compose_ds."""
    import rerun as rr
    import rerun.blueprint as rrb

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    recording = rr.RecordingStream(application_id, make_default=False, make_thread_default=False)
    recording.disable_timeline("log_time")
    recording.save(str(output))
    sink = RerunSink(recording=recording)
    lowered = lower(root, sink, name=application_id)
    blueprint = rrb.Blueprint(
        lowered.view, auto_layout=False, auto_views=False, collapse_panels=True
    )
    recording.send_blueprint(blueprint, make_active=True, make_default=True)
    recording.flush()
    return output, lowered


# ---------------------------------------------------------------------------
# Vocabulary collapse: the exact mapping tables (evidence for the findings comment)
# ---------------------------------------------------------------------------

# ComposeType member -> Channel. Total; `sequence` ALWAYS means TIME. The old four-way
# ambiguity ("Tabs in panel, temporal concat in video") resolves because panel's
# capability table marks TIME Unsupported and the documented substitution chain
# (already in bencher.grammar) lands it on TABS; video and rerun lower TIME natively.
COMPOSE_TYPE_TO_CHANNEL: dict[ComposeType, Channel] = {
    ComposeType.right: Channel.FACET_COL,
    ComposeType.down: Channel.FACET_ROW,
    ComposeType.overlay: Channel.OVERLAY,
    ComposeType.sequence: Channel.TIME,
}


def channel_of_compose_type(compose_type: ComposeType) -> Channel:
    """The deprecation shim's core: total, one-line-per-member, no policy."""
    return COMPOSE_TYPE_TO_CHANNEL[ComposeType(compose_type)]


def pane_layout_channels(layout: PaneLayout, num_levels: int) -> list[Channel]:
    """PaneLayout member -> Channel assignment per facet level (outermost first).

    PaneLayout is NOT a channel — it is a channel-assignment *policy* for the facet
    pool (A6 Law 7 step 5's 'grid/tabs preference knob'). It collapses into the
    planner's default assignment, not into the Channel enum.
    """
    if layout is PaneLayout.grid:
        return default_facet_channels(num_levels)
    if layout is PaneLayout.tabs:
        # tabs for all outer levels, innermost grid
        if num_levels <= 1:
            return default_facet_channels(num_levels)
        return [Channel.TABS] * (num_levels - 1) + default_facet_channels(1)
    if layout is PaneLayout.tabs_and_grid:
        if num_levels <= 1:
            return default_facet_channels(num_levels)
        return [Channel.TABS] + default_facet_channels(num_levels - 1)
    raise AssertionError(layout)  # pragma: no cover


def default_facet_channels(num_levels: int, time_levels: int = 0) -> list[Channel]:
    """The minimal default replacing compose_method_list_for_dims (outermost first).

    Alternate FACET_ROW/FACET_COL so nested dims stay readable — the surviving half of
    the old policy. The old *trailing* unconditional `sequence` does NOT survive as a
    compose level: the innermost 'level' is the leaf's own X/timeline now, owned by
    the leaf lowering. `time_levels=-1` sequences everything (old
    time_sequence_dimension=-1); `time_levels=k` forces the first k levels to TIME.
    """
    if time_levels == -1:
        return [Channel.TIME] * num_levels
    out: list[Channel] = []
    axis = Channel.FACET_ROW
    for _ in range(num_levels):
        out.append(axis)
        axis = Channel.FACET_COL if axis is Channel.FACET_ROW else Channel.FACET_ROW
    for i in range(min(num_levels, time_levels)):
        out[i] = Channel.TIME
    return out


# ---------------------------------------------------------------------------
# The three adapters: how each existing builder's input maps into the one recursion
# ---------------------------------------------------------------------------


def from_sweep_dataset(
    dataset: xr.Dataset,
    result_vars: list,
    float_dims: list[str],
    cat_dims: list[str],
    time_channel_dims: tuple[str, ...] = (),
) -> Node:
    """Builder 1's input (rerun_result: a dataset of VALUES) -> a Compose tree.

    Replaces BOTH _log_to_rerun and _build_blueprint_contents/_recurse/
    _peel_dim_as_grid/_make_leaf_view: the peel order is the planner-stub here; the
    lowering is the shared recursion. `time_channel_dims` are dims assigned to the
    TIME channel (the generalization of over_time — each gets its OWN named timeline).
    """

    def build(ds: xr.Dataset, fd: list[str], cd: list[str], rv, depth: int) -> Node:
        # over_time generalized: any TIME-assigned dim peels as Compose(along=TIME)
        for td in time_channel_dims:
            if td in ds.dims and (td in fd or td in cd):
                fd2 = [d for d in fd if d != td]
                cd2 = [d for d in cd if d != td]
                slots = [
                    Slot(
                        key=f"{td}={v}",
                        node=build(ds.sel({td: v}), fd2, cd2, rv, depth),
                        coord=float(v) if not _is_cat(ds, td) else i,
                    )
                    for i, v in enumerate(ds.coords[td].values)
                ]
                return Compose(items=tuple(slots), along=Channel.TIME)
        # Phase A: peel cats as facets (all of them if floats remain; else until 1
        # is left for the BarChart axis) — same policy as today's phases.
        if cd and (fd or len(cd) > 1):
            dim = cd[-1]
            axis = Channel.FACET_COL if depth % 2 == 0 else Channel.FACET_ROW
            slots = [
                Slot(key=f"{dim}={v}", node=build(ds.sel({dim: v}), fd, cd[:-1], rv, depth + 1))
                for v in ds.coords[dim].values
            ]
            return Compose(items=tuple(slots), along=axis)
        # Phase B: peel extra floats until <= 3 remain for the leaf
        if len(fd) + len(cd) > 3:
            dim = fd[-1]
            axis = Channel.FACET_COL if depth % 2 == 0 else Channel.FACET_ROW
            slots = [
                Slot(key=f"{dim}={v}", node=build(ds.sel({dim: v}), fd[:-1], [], rv, depth + 1))
                for v in ds.coords[dim].values
            ]
            return Compose(items=tuple(slots), along=axis)
        return DatasetLeaf(dataset=ds, result_var=rv)

    trees = [
        Slot(
            key=(rv.name if hasattr(rv, "name") else str(rv)),
            node=build(dataset, list(float_dims), list(cat_dims), rv, 0),
        )
        for rv in result_vars
    ]
    if len(trees) == 1:
        return trees[0].node
    # Law 5: one plan per result var, composed by an outer layout node.
    return Compose(items=tuple(trees), along=Channel.FACET_ROW)


def from_blob_dataset(
    dataset: xr.Dataset,
    result_var,
    channels: list[Channel] | None = None,
    time_levels: int = 0,
) -> Node | None:
    """Builder 2's input (rerun_summary._compose_ds: a dataset of .rrd PATHS) -> the
    same Compose tree, with BlobLeaf leaves. One dim peeled per level, outermost
    last-declared first — but NO intermediate .rrd per level: leaves splice into the
    single host recording."""
    rv_name = result_var.name if hasattr(result_var, "name") else str(result_var)
    dims = list(dataset[rv_name].dims)
    if channels is None:
        channels = default_facet_channels(len(dims), time_levels=time_levels)

    def build(ds: xr.Dataset, level: int) -> Node | None:
        rem = list(ds[rv_name].dims)
        if not rem:
            value = ds[rv_name].values.item()
            if result_is_missing(result_var, value):
                return None
            path = Path(str(value))
            if not path.is_file():
                logger.debug("rerun recording %s missing on disk", path)
                return None
            return BlobLeaf(path=path)
        dim = rem[-1]  # outermost = last-declared, matching _compose_ds
        slots = []
        for i, v in enumerate(ds.coords[dim].values):
            child = build(ds.sel({dim: v}), level + 1)
            if child is None:
                continue
            slots.append(Slot(key=f"{dim}={v}", node=child, coord=i))
        if not slots:
            return None
        return Compose(items=tuple(slots), along=channels[level])

    return build(dataset, 0)


def from_flat_list(
    paths: list[str | Path],
    along: Channel | ComposeType | str,
    labels: list[str] | None = None,
) -> Node:
    """Builder 3's input (ComposableContainerRerun: a flat LIST of .rrd paths) ->
    one Compose level. `along` accepts a legacy ComposeType via the shim — exactly
    the deprecation surface PR #1007's append() keeps."""
    if isinstance(along, ComposeType) or (
        isinstance(along, str) and along in ComposeType.__members__
    ):
        along = channel_of_compose_type(ComposeType(along))
    slots = tuple(
        Slot(key=(labels[i] if labels else str(i)), node=BlobLeaf(path=p), coord=i)
        for i, p in enumerate(paths)
    )
    return Compose(items=slots, along=Channel(along))
