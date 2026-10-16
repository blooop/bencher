"""The one composition algebra — A6 Law 4.

A `Compose` node is items plus a layout channel. It replaces the four-way-ambiguous
`ComposeType.{right,down,sequence,overlay}` encoding (`sequence` means Tabs in
panel/rerun but temporal concatenation in video) with the same channel vocabulary that
assigns sweep dimensions, so report structure and within-plot structure are one algebra.

Two producers exist in the design; only one exists here. The **user** builds `Compose`
directly — ``compose([a, b, c], along="facet_col")`` — over any ad-hoc collection. The
**planner** producer (items from slicing a sweep dim) arrives with A6 phase 3.

How a `Compose` evaluates — ``view`` (a live backend view) or ``materialize`` (a blob
cell) — is a property of the backend capability table (`capability.py`), never a field
on the node itself (Law 4).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from bencher.grammar.channels import Channel


@dataclass(frozen=True)
class Compose:
    """Items laid out along one channel.

    Items are opaque to the grammar — renditions, report items, or nested `Compose`
    nodes; the grammar never imports a rendering type (the direction-of-import rule).
    """

    items: tuple[object, ...]
    along: Channel

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("Compose of zero items has no meaning; give at least one item")


def compose(items: Iterable[object], along: Channel | str) -> Compose:
    """User-facing producer: ``compose([a, b, c], along="facet_col")``."""
    return Compose(items=tuple(items), along=Channel(along))
