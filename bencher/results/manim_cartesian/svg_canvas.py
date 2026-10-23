"""Minimal SVG drawing surface for the Cartesian product animation.

The shapes draw through a handful of calls -- rectangles, lines, text and placing a
shared sub-drawing -- so this is all the SVG the animation needs. A sub-drawing that
recurs (every copy an extrusion makes is identical) is written once into ``<defs>``
and placed with ``<use>``, so the file grows with the number of *distinct* shapes,
not with the number of cells on screen.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence

Color = tuple[int, ...]

# Pillow placed text by the top of its ascender; SVG places the baseline. The shapes
# keep Pillow's convention, so text() moves y down by the ascent of the bold sans
# fonts the animation asks for (DejaVu Sans Bold's ascender is 0.93 em).
TEXT_ASCENT = 0.93
FONT_FAMILY = "DejaVu Sans, Verdana, Arial, sans-serif"


def _hex(color: Color) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(c) for c in color[:3]))


def _num(value: float) -> str:
    """Shortest decimal for ``value`` at 0.01 px, which is below anything visible."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def content_key(*parts: object) -> str:
    """Short digest naming a drawing by its content, for sharing it through ``<defs>``."""
    return hashlib.md5(repr(parts).encode(), usedforsecurity=False).hexdigest()[:16]


class SvgDefs:
    """The ``<defs>`` of one document: each distinct sub-drawing, defined once."""

    def __init__(self, id_prefix: str) -> None:
        self._prefix = id_prefix
        self._ids: dict[str, str] = {}
        self._parts: list[str] = []

    def define(self, key: str, draw: Callable[[SvgCanvas], None]) -> str:
        """Return the id of the drawing named ``key``, drawing it on first use."""
        ref = self._ids.get(key)
        if ref is None:
            canvas = SvgCanvas(self)
            draw(canvas)
            ref = f"{self._prefix}{len(self._ids):x}"
            self._ids[key] = ref
            self._parts.append(f'<g id="{ref}">{canvas.markup()}</g>')
        return ref

    def markup(self) -> str:
        return f"<defs>{''.join(self._parts)}</defs>" if self._parts else ""


class SvgCanvas:
    """A list of SVG elements, drawn with the subset of Pillow's ImageDraw API the shapes use.

    Coordinates follow Pillow: a box ``[x0, y0, x1, y1]`` covers pixels x0..x1
    inclusive, and an outline of width ``w`` lies inside the box.
    """

    def __init__(self, defs: SvgDefs) -> None:
        self.defs = defs
        self._parts: list[str] = []

    def rectangle(
        self,
        box: Sequence[float],
        fill: Color | None = None,
        outline: Color | None = None,
        width: int = 1,
        radius: float = 0,
        opacity: float | None = None,
    ) -> None:
        x0, y0, x1, y1 = box
        inset = width / 2 if outline is not None else 0
        grow = 0 if outline is not None else 1  # Pillow fills x1 itself
        attrs = (
            f'x="{_num(x0 + inset)}" y="{_num(y0 + inset)}"'
            f' width="{_num(x1 - x0 + grow - 2 * inset)}"'
            f' height="{_num(y1 - y0 + grow - 2 * inset)}"'
        )
        if radius:
            attrs += f' rx="{_num(radius)}"'
        attrs += f' fill="{_hex(fill)}"' if fill is not None else ' fill="none"'
        if opacity is not None:
            attrs += f' fill-opacity="{_num(opacity * 100)}%"'
        if outline is not None:
            attrs += f' stroke="{_hex(outline)}"'
            if width != 1:
                attrs += f' stroke-width="{width}"'
        self._parts.append(f"<rect {attrs}/>")

    def line(
        self,
        xy: Sequence[float],
        fill: Color,
        width: int = 1,
        dash: tuple[float, float] | None = None,
    ) -> None:
        """Draw a line; ``dash`` is ``(on, off)`` lengths for a dashed one."""
        x0, y0, x1, y1 = xy
        stroke_w = f' stroke-width="{width}"' if width != 1 else ""
        if dash is not None:
            stroke_w += f' stroke-dasharray="{_num(dash[0])} {_num(dash[1])}"'
        self._parts.append(
            f'<line x1="{_num(x0)}" y1="{_num(y0)}" x2="{_num(x1)}" y2="{_num(y1)}"'
            f' stroke="{_hex(fill)}"{stroke_w}/>'
        )

    def text(self, x: float, y: float, label: str, size: int, fill: Color) -> None:
        """Draw ``label`` centred on ``x``, with the top of its ascender at ``y``."""
        self._parts.append(
            f'<text x="{_num(x)}" y="{_num(y + size * TEXT_ASCENT)}" font-size="{size}"'
            f' fill="{_hex(fill)}" text-anchor="middle">{escape(label)}</text>'
        )

    def place(
        self,
        key: str,
        draw: Callable[[SvgCanvas], None],
        x: float,
        y: float,
        scale: float = 1.0,
    ) -> None:
        """Place the shared drawing named ``key`` (drawn at the origin) at ``(x, y)``."""
        ref = self.defs.define(key, draw)
        if scale == 1.0:
            pos = (f' x="{_num(x)}"' if x else "") + (f' y="{_num(y)}"' if y else "")
            self._parts.append(f'<use href="#{ref}"{pos}/>')
        else:
            self._parts.append(
                f'<use href="#{ref}" transform="translate({_num(x)} {_num(y)})'
                f' scale({scale:.4g})"/>'
            )

    @contextmanager
    def transformed(self, x: float, y: float, scale: float = 1.0) -> Generator[SvgCanvas]:
        """Draw the body into a group translated to ``(x, y)`` and scaled by ``scale``."""
        transform = f"translate({_num(x)} {_num(y)})"
        if scale != 1.0:
            transform += f" scale({scale:.4g})"
        self._parts.append(f'<g transform="{transform}">')
        try:
            yield self
        finally:
            self._parts.append("</g>")

    def markup(self) -> str:
        return "".join(self._parts)


def animated_svg(
    defs: SvgDefs, frames: list[tuple[str, int]], width: int, height: int, background: Color
) -> str:
    """Assemble frames of ``(markup, duration_ms)`` into one looping SMIL animation.

    Each frame is a group that a discrete ``<animate>`` shows for its slot of the
    loop. The last frame is visible by default, so a viewer without SMIL (or a
    static rasteriser) shows the finished product rather than a blank canvas.
    """
    merged: list[tuple[str, int]] = []
    for body, duration in frames:
        if merged and merged[-1][0] == body:
            merged[-1] = (body, merged[-1][1] + duration)
        else:
            merged.append((body, duration))

    total = sum(d for _, d in merged)
    groups = []
    start = 0
    for i, (body, duration) in enumerate(merged):
        default = "visible" if i == len(merged) - 1 else "hidden"
        if len(merged) == 1:
            groups.append(f"<g>{body}</g>")
            break
        k0, k1 = start / total, (start + duration) / total
        key_times = [0.0] + ([k0] if k0 > 0 else []) + ([k1] if k1 < 1 else [])
        values = (["hidden"] if k0 > 0 else []) + ["visible"] + (["hidden"] if k1 < 1 else [])
        groups.append(
            f'<g visibility="{default}"><animate attributeName="visibility"'
            f' dur="{total / 1000:.3f}s" repeatCount="indefinite" calcMode="discrete"'
            f' keyTimes="{";".join(f"{k:.4f}".rstrip("0").rstrip(".") for k in key_times)}"'
            f' values="{";".join(values)}"/>{body}</g>'
        )
        start += duration

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}" font-family="{FONT_FAMILY}" font-weight="bold">'
        f"{defs.markup()}"
        f'<rect width="{width}" height="{height}" fill="{_hex(background)}"/>'
        f"{''.join(groups)}</svg>"
    )
