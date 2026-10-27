"""Backend capability tables and planner-owned fallback — A6 Law 3.

Each backend exports a static table: per channel, one of `Native | Approx |
Unsupported` (the arm *is* Law 3's fidelity ``native | approx | none`` — no separate
tag to drift out of sync). Fallback belongs to the planner side via one documented
substitution chain; backends are dumb translators and never degrade on their own
(Law 3 rejects backend-owned degradation as re-scattering the knowledge).

With no planner yet, the embryo is `substitute()`: a pure, table-driven function the
phase-3 planner absorbs unchanged (plan 25 amendment). The **rerun** table seeds it
because rerun is the backend the current route builds; the panel table joins in
phase 3, when `marks.py` absorbs the table type per plan 25 D1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import assert_never

from strenum import StrEnum

from bencher.grammar.channels import Channel


class EvalMode(StrEnum):
    """How a `Compose` along a channel evaluates on this backend — A6 Law 4.

    ``view`` is a live backend view; ``materialize`` is a blob cell (webm, merged rrd,
    parquet; content-addressed per Law 1). A backend/medium property carried by the
    capability entry, never by the `Compose` node.
    """

    VIEW = "view"
    MATERIALIZE = "materialize"


@dataclass(frozen=True)
class Native:
    """Full-fidelity lowering."""

    mode: EvalMode


@dataclass(frozen=True)
class Approx:
    """Lowers with a visible degradation, stated so `explain()` (phase 3) can show it."""

    mode: EvalMode
    how: str


@dataclass(frozen=True)
class Unsupported:
    """No lowering: the substitution chain is the only route."""

    why: str


Capability = Native | Approx | Unsupported


@dataclass(frozen=True)
class BackendCapabilities:
    """One backend's static table, total over the vocabulary by construction: a missing
    channel is a constructor error, not a `KeyError` at plan time."""

    backend: str
    channels: Mapping[Channel, Capability]

    def __post_init__(self) -> None:
        missing = set(Channel) - set(self.channels)
        if missing:
            names = ", ".join(sorted(c.name for c in missing))
            raise ValueError(f"capability table for {self.backend!r} misses channels: {names}")


# The documented substitution chain (Law 3) — exactly the substitutions A6 states:
# Time → Tabs (Law 3's example), Overlay → FacetCol (Law 5's shared-frame fallback),
# Spread → Overlay (§3's declared rerun gap). Extending this mapping is a grammar
# change: document the ruling first.
SUBSTITUTION_CHAIN: dict[Channel, Channel] = {
    Channel.TIME: Channel.TABS,
    Channel.OVERLAY: Channel.FACET_COL,
    Channel.SPREAD: Channel.OVERLAY,
}


@dataclass(frozen=True)
class Direct:
    """The requested channel lowers as-is."""

    channel: Channel
    capability: Native | Approx


@dataclass(frozen=True)
class Substituted:
    """The requested channel lowers via the chain. `via` is the full walk — requested
    channel first, landing channel last, length >= 2 — recorded so a plan can surface
    it in `explain()` (Law 3: substitutions are visible, never silent)."""

    channel: Channel
    via: tuple[Channel, ...]
    capability: Native | Approx


@dataclass(frozen=True)
class NoLowering:
    """The chain ran out before reaching a supported channel."""

    requested: Channel
    reason: str


Lowering = Direct | Substituted | NoLowering


def substitute(table: BackendCapabilities, requested: Channel) -> Lowering:
    """Resolve `requested` against one backend's table, walking the documented chain on
    `Unsupported`. Total: every (table, channel) pair returns one of the three arms."""
    walked: list[Channel] = [requested]
    current = requested
    reasons: list[str] = []
    while True:
        cap = table.channels[current]
        match cap:
            case Native() | Approx():
                if current is requested:
                    return Direct(channel=current, capability=cap)
                return Substituted(channel=current, via=tuple(walked), capability=cap)
            case Unsupported(why=why):
                reasons.append(f"{current}: {why}")
                nxt = SUBSTITUTION_CHAIN.get(current)
                if nxt is None or nxt in walked:
                    return NoLowering(requested=requested, reason="; ".join(reasons))
                walked.append(nxt)
                current = nxt
            case _ as unreachable:
                assert_never(unreachable)


# Seed table: rerun — A6 §3's parity table made typed, refined by the measured
# lowering-gaps dossier (issue #1110). Everything rerun shows is a live view; the
# materialize mode arrives with the video backend (Law 10 phase 4b).
RERUN_CAPABILITIES = BackendCapabilities(
    backend="rerun",
    channels={
        # SeriesLines / points on a timeline (§3: native).
        Channel.X: Native(mode=EvalMode.VIEW),
        Channel.Y: Native(mode=EvalMode.VIEW),
        # Heatmap/volume lower to rr.Tensor views (§3: native/approx) — a sliceable
        # tensor, not a 3D surface mark.
        Channel.Z: Approx(mode=EvalMode.VIEW, how="lowers to rr.Tensor views; no 3D surface mark"),
        # Sibling entity paths in a shared view (§3: native).
        Channel.OVERLAY: Native(mode=EvalMode.VIEW),
        # rrb.Vertical / Horizontal / Tabs containers (§3: native).
        Channel.FACET_ROW: Native(mode=EvalMode.VIEW),
        Channel.FACET_COL: Native(mode=EvalMode.VIEW),
        Channel.TABS: Native(mode=EvalMode.VIEW),
        # A named timeline per Time dim (§3: native).
        Channel.TIME: Native(mode=EvalMode.VIEW),
        # §3's declared gap: no native mean±std band view.
        Channel.SPREAD: Unsupported(why="no native band view (A6 §3 declared gap)"),
    },
)
