"""Dimensional extrusion animation using PIL.

Shows how each dimension builds on the last:
    point --dim1--> line --dim2--> grid --dim3--> stack
    --repeat--> extrude --over_time--> film strip
    --dim4+--> sets of sets ...

Renders frames directly with PIL (fast), saves as GIF.
"""

from __future__ import annotations

import functools
import hashlib
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bencher.results.manim_cartesian.cartesian_product_cfg import CartesianProductCfg

logger = logging.getLogger(__name__)

# Layout — light theme to match white page background
CELL_SIZE = 20
CELL_GAP = 3
# Curated 10-color palette — pastel, distinct on white, cycles after 10
DIM_PALETTE = [
    (150, 190, 240),  # blue
    (240, 160, 155),  # red
    (150, 220, 160),  # green
    (245, 225, 140),  # yellow
    (220, 170, 235),  # purple
    (245, 200, 150),  # orange
    (170, 225, 225),  # cyan
    (240, 180, 200),  # pink
    (200, 215, 155),  # lime
    (200, 185, 230),  # lavender
]
CELL_BORDER = (180, 180, 180)
BG_COLOR = (255, 255, 255)  # white
LABEL_COLOR = (30, 30, 30)  # dark text
DEPTH_DX = 10
DEPTH_DY = -8
GROUP_GAP = 20
GAP = "..."


def _create_cache_key(
    cfg: CartesianProductCfg, width: int, height: int, fps: int, step_frames: int
) -> str:
    """Create a deterministic cache key from animation parameters."""
    # Convert cfg to a hashable string representation
    cfg_str = (
        f"vars:{[(v.name, tuple(v.values)) for v in cfg.all_vars]}"
        f"results:{tuple(cfg.result_names)}"
        f"strobe_color:{cfg.strobe_color}"
        f"strobe_pad:{cfg.strobe_pad}"
        f"strobe_mark_size:{cfg.strobe_mark_size}"
        f"strobe_mark_gap:{cfg.strobe_mark_gap}"
        f"strobe_mark_row_h:{cfg.strobe_mark_row_h}"
        f"strobe_border_radius:{cfg.strobe_border_radius}"
        f"strobe_base_border_w:{cfg.strobe_base_border_w}"
    )

    params_str = f"{cfg_str}|w:{width}|h:{height}|fps:{fps}|steps:{step_frames}"
    return hashlib.md5(params_str.encode()).hexdigest()[:12]  # 12 chars for readability


@functools.lru_cache(maxsize=8)
def _get_font(size: int):
    """Get a font, falling back to default if no TTF available."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except (OSError, IOError):
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", size
            )
        except (OSError, IOError):
            return ImageFont.load_default()


class Shape:
    """Recursive shape representation for dimensional extrusion.

    A Shape is either a leaf (single cell) or a collection of sub-shapes
    arranged along an axis.  ``depth`` tracks nesting level so that
    higher-dimensional extrusions use wider gaps.
    """

    def __init__(
        self,
        children: list["Shape"] | None = None,
        direction: str = "right",
        depth: int = 0,
        color_index: int = 0,
    ):
        self.children = children  # None = leaf cell
        self.direction = direction  # right, down, stack
        self.depth = depth  # 0 = innermost (tight gap), higher = wider gap
        self.color_index = color_index  # palette index for leaf cells
        self._cached_size = None  # lazily populated by size()

    @property
    def is_leaf(self) -> bool:
        return self.children is None

    @property
    def gap(self) -> int:
        """Gap between children.

        Depth 0-2 (first two spatial dims forming the basic grid): tight CELL_GAP.
        Depth 3 (stack direction): uses isometric offset, gap not used.
        Depth 4+ (sets of stacks, sets of sets): GROUP_GAP scaling with depth.
        """
        if self.depth <= 2:
            return CELL_GAP
        return GROUP_GAP * max(1, self.depth - 3)

    def size(self) -> tuple[int, int]:
        """Return (width, height) in pixels.  Cached — tree structure is immutable."""
        if self._cached_size is not None:
            return self._cached_size
        if self.is_leaf:
            result = (CELL_SIZE, CELL_SIZE)
        elif self.direction == "stack":
            cw, ch = self.children[0].size()
            n = len(self.children)
            result = (cw + (n - 1) * DEPTH_DX, ch + (n - 1) * abs(DEPTH_DY))
        elif self.direction == "right":
            g = self.gap
            w = sum(c.size()[0] for c in self.children) + g * (len(self.children) - 1)
            h = max(c.size()[1] for c in self.children)
            result = (w, h)
        else:  # down
            g = self.gap
            w = max(c.size()[0] for c in self.children)
            h = sum(c.size()[1] for c in self.children) + g * (len(self.children) - 1)
            result = (w, h)
        self._cached_size = result
        return result

    def draw(self, img: ImageDraw.ImageDraw, x: int, y: int, alpha: float = 1.0):
        """Draw this shape at position (x, y) on the image."""
        if self.is_leaf:
            base = DIM_PALETTE[self.color_index % len(DIM_PALETTE)]
            color = tuple(int(c * alpha) for c in base)
            border = tuple(int(c * alpha) for c in CELL_BORDER)
            img.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], fill=color, outline=border)
            return
        if self.direction == "stack":
            # Isometric 3D stack: back layers at top-right, front at bottom-left.
            # Draw back-to-front (painter's algorithm) with depth dimming.
            n = len(self.children)
            for i in range(n):
                cx = x + (n - 1 - i) * DEPTH_DX
                cy = y + i * abs(DEPTH_DY)
                dim_factor = 0.5 + 0.5 * i / max(n - 1, 1)
                self.children[i].draw(img, cx, cy, alpha * dim_factor)
            return
        g = self.gap
        if self.direction == "right":
            cx = x
            for child in self.children:
                child.draw(img, cx, y, alpha)
                cx += child.size()[0] + g
        else:  # down
            cy = y
            for child in self.children:
                child.draw(img, x, cy, alpha)
                cy += child.size()[1] + g

    def extrude(self, n: int, direction: str, color_index: int | None = None) -> "Shape":
        """Create a new shape by extruding this one n times along direction."""
        if color_index is not None:
            copies = [self._deep_copy_recolored(color_index) for _ in range(n)]
        else:
            copies = [self._deep_copy() for _ in range(n)]
        return Shape(children=copies, direction=direction, depth=self.depth + 1)

    def _deep_copy(self) -> "Shape":
        if self.is_leaf:
            return Shape(color_index=self.color_index)
        return Shape(
            children=[c._deep_copy() for c in self.children],
            direction=self.direction,
            depth=self.depth,
        )

    def _deep_copy_recolored(self, color_index: int) -> "Shape":
        """Copy and recolor in a single traversal."""
        if self.is_leaf:
            return Shape(color_index=color_index)
        return Shape(
            children=[c._deep_copy_recolored(color_index) for c in self.children],
            direction=self.direction,
            depth=self.depth,
        )


# Dimensions 0-1: right/down to form 2D grid.
# Dimension 2: "stack" for isometric 3D effect.
# Dimensions 3+: resume right/down alternation for sets/groups.
def _direction_for(dim_index: int) -> str:
    """Map dimension index to layout direction."""
    if dim_index == 2:
        return "stack"
    return "right" if dim_index % 2 == 0 else "down"


# --- Film-strip timeline for over_time ---
# Proportions modelled on 35mm film: sprocket holes are tall, narrow,
# closely spaced, and take up most of the border between strip edge and frame.
FILM_COLOR = (35, 35, 38)  # dark film stock — contrasts with white page
FILM_EDGE = (25, 25, 28)  # darker outline
FILM_FRAME_BORDER = (90, 90, 95)  # frame outline
FILM_LABEL_COLOR = (100, 100, 100)  # subdued labels on white bg
FILM_PAD = 6  # thin strip edge padding
FILM_FRAME_PAD = 10  # padding inside each frame around the shape
FILM_FRAME_GAP = 16  # gap between frames
FILM_SPROCKET_W = 8  # narrow
FILM_SPROCKET_H = 14  # tall — real film sprockets are taller than wide
FILM_SPROCKET_R = 2  # corner radius
FILM_SPROCKET_SPACING = 14  # closely spaced like real film
FILM_SPROCKET_MARGIN = 4  # small gap between sprocket row and frames
FILM_LABEL_H = 18  # space for frame labels below strip


class TimelineShape(Shape):
    """Film-strip timeline for the over_time dimension.

    Each time step is a "frame" in a horizontal film strip with
    sprocket holes along top and bottom edges — unmistakably film.

    The film chrome (sprockets, borders, padding) is always rendered at
    a fixed pixel size.  The inner shape is scaled to fit within a
    constant frame window so the strip looks the same regardless of
    content complexity.
    """

    # Fixed pixel size per film frame window (inner content area).
    FRAME_W = 100
    FRAME_H = 80

    def __init__(self, inner: Shape, count: int):
        self.inner = inner
        self.count = count
        super().__init__(children=None, direction="right", depth=0)

    @property
    def is_leaf(self) -> bool:
        return False

    def _outer_frame_size(self) -> tuple[int, int]:
        """Size of each frame including padding."""
        return (FILM_FRAME_PAD * 2 + self.FRAME_W, FILM_FRAME_PAD * 2 + self.FRAME_H)

    def size(self) -> tuple[int, int]:
        frame_w, frame_h = self._outer_frame_size()

        total_w = FILM_PAD * 2 + self.count * frame_w + (self.count - 1) * FILM_FRAME_GAP
        total_h = (
            FILM_PAD
            + FILM_SPROCKET_H
            + FILM_SPROCKET_MARGIN
            + frame_h
            + FILM_SPROCKET_MARGIN
            + FILM_SPROCKET_H
            + FILM_PAD
            + FILM_LABEL_H
        )
        return (total_w, total_h)

    def draw(self, img: ImageDraw.ImageDraw, x: int, y: int, alpha: float = 1.0):
        frame_w, frame_h = self._outer_frame_size()
        total_w, total_h = self.size()
        strip_h = total_h - FILM_LABEL_H

        # --- Film strip background ---
        img.rounded_rectangle(
            [x, y, x + total_w, y + strip_h], radius=4, fill=FILM_COLOR, outline=FILM_EDGE
        )

        # --- Sprocket holes (top and bottom) ---
        sprocket_y_top = y + FILM_PAD
        sprocket_y_bot = y + strip_h - FILM_PAD - FILM_SPROCKET_H
        self._draw_sprockets(img, x, sprocket_y_top, total_w)
        self._draw_sprockets(img, x, sprocket_y_bot, total_w)

        # --- Pre-render inner shape once, then paste into each frame ---
        iw, ih = self.inner.size()
        scale = min(self.FRAME_W / max(iw, 1), self.FRAME_H / max(ih, 1), 1.0)
        inner_img = Image.new("RGB", (max(iw, 1), max(ih, 1)), BG_COLOR)
        inner_draw = ImageDraw.Draw(inner_img)
        self.inner.draw(inner_draw, 0, 0, alpha)
        if scale < 1.0:
            inner_img = inner_img.resize((int(iw * scale), int(ih * scale)), Image.Resampling.LANCZOS)
        scaled_w, scaled_h = inner_img.size

        # Need the underlying PIL Image (not ImageDraw) for pasting
        base_img = img._image

        frames_y = y + FILM_PAD + FILM_SPROCKET_H + FILM_SPROCKET_MARGIN
        font_label = _get_font(12)

        for i in range(self.count):
            fx = x + FILM_PAD + i * (frame_w + FILM_FRAME_GAP)

            # Frame cutout
            img.rounded_rectangle(
                [fx, frames_y, fx + frame_w, frames_y + frame_h],
                radius=2,
                fill=BG_COLOR,
                outline=FILM_FRAME_BORDER,
            )

            # Paste inner shape centered in the frame window
            cx = fx + FILM_FRAME_PAD + (self.FRAME_W - scaled_w) // 2
            cy = frames_y + FILM_FRAME_PAD + (self.FRAME_H - scaled_h) // 2
            base_img.paste(inner_img, (cx, cy))

            # Frame number label below the strip
            label = f"t={i}"
            bbox = img.textbbox((0, 0), label, font=font_label)
            tw = bbox[2] - bbox[0]
            lx = fx + (frame_w - tw) // 2
            img.text((lx, y + strip_h + 2), label, fill=FILM_LABEL_COLOR, font=font_label)

    @staticmethod
    def _draw_sprockets(img: ImageDraw.ImageDraw, strip_x: int, row_y: int, strip_w: int):
        """Draw a row of rounded sprocket holes across the strip width."""
        margin = FILM_PAD + 6
        avail = strip_w - 2 * margin
        n = max(1, int(avail / FILM_SPROCKET_SPACING))
        actual_spacing = avail / max(n, 1)

        for j in range(n + 1):
            sx = strip_x + margin + j * actual_spacing - FILM_SPROCKET_W // 2
            img.rounded_rectangle(
                [sx, row_y, sx + FILM_SPROCKET_W, row_y + FILM_SPROCKET_H],
                radius=FILM_SPROCKET_R,
                fill=BG_COLOR,
            )

    def _deep_copy(self) -> "Shape":
        return TimelineShape(self.inner._deep_copy(), self.count)


# ---------------------------------------------------------------------------
# Repeat animation — strobe / flash
# ---------------------------------------------------------------------------


class StrobeShape(Shape):
    """Shape with a glowing border and tally-mark counter.

    ``flash`` (0–1) controls the glow intensity for animation frames.
    All visual tunables are read from ``cfg`` (a CartesianProductCfg).
    """

    def __init__(self, inner: Shape, count: int, cfg: CartesianProductCfg, flash: float = 0.0):
        self.inner = inner
        self.count = count
        self.cfg = cfg
        self.flash = flash
        super().__init__(children=None, direction="right", depth=0)

    @property
    def is_leaf(self) -> bool:
        return False

    def size(self) -> tuple[int, int]:
        iw, ih = self.inner.size()
        c = self.cfg
        # Marks never widen the box — they overlap if needed
        total_w = iw + 2 * c.strobe_pad
        total_h = ih + 2 * c.strobe_pad + c.strobe_mark_row_h
        return (total_w, total_h)

    def draw(self, img: ImageDraw.ImageDraw, x: int, y: int, alpha: float = 1.0):
        c = self.cfg
        iw, ih = self.inner.size()
        total_w, total_h = self.size()
        box_h = total_h - c.strobe_mark_row_h

        # Border — static (no flash)
        border_color = tuple(int(v * 0.25 * alpha) for v in c.strobe_color)
        img.rounded_rectangle(
            [x, y, x + total_w, y + box_h],
            radius=c.strobe_border_radius,
            outline=border_color,
            width=c.strobe_base_border_w,
        )

        # Inner shape
        ix = x + (total_w - iw) // 2
        iy = y + (box_h - ih) // 2
        self.inner.draw(img, ix, iy, alpha)

        # Gentle gray wash on flash
        if self.flash > 0.3:
            fill_alpha = self.flash * 0.08
            overlay = Image.new("RGB", (total_w, box_h), c.strobe_color)
            base_img = img._image
            base_img.paste(
                Image.blend(base_img.crop((x, y, x + total_w, y + box_h)), overlay, fill_alpha),
                (x, y),
            )

        # Tally marks + count label below
        marks_y = y + box_h + 6
        mark_color = tuple(int(v * alpha) for v in c.strobe_color)
        avail_w = total_w - 2 * c.strobe_pad
        self._draw_tally(img, x + c.strobe_pad, marks_y, avail_w, mark_color, c)

    def _draw_tally(self, img, mx0, my, avail_w, color, c):
        """Proper tally marks (vertical lines, diagonal strike every 5) + xN label.

        Tallies grow from the left. The xN number is always on the right.
        Only draws as many complete groups/marks as fit cleanly; the label
        alone conveys the count when space is tight.
        """
        mark_h = c.strobe_mark_row_h - 2
        mark_w = c.strobe_mark_size
        stride = mark_w + c.strobe_mark_gap
        group_size = 5
        group_gap = c.strobe_mark_gap * 3

        font = _get_font(c.strobe_mark_row_h - 2)
        one_group_w = (group_size - 1) * stride + mark_w

        # Check if all tallies fit
        def tally_width(n):
            if n == 0:
                return 0
            n_full = n // group_size
            n_rem = n % group_size
            w = n_full * one_group_w + max(0, n_full - 1) * group_gap
            if n_rem > 0:
                w += (group_gap if n_full > 0 else 0) + (n_rem - 1) * stride + mark_w
            return w

        if tally_width(self.count) <= avail_w:
            # All tallies fit — draw them, no number needed
            cx = mx0
            for i in range(self.count):
                group_idx = i % group_size
                img.rectangle([cx, my, cx + mark_w, my + mark_h], fill=color)
                if group_idx == group_size - 1:
                    group_x0 = cx - (group_size - 1) * stride
                    overshoot = stride // 2
                    inset = mark_h // 5
                    img.line(
                        [
                            group_x0 - overshoot,
                            my + mark_h - inset,
                            cx + mark_w + overshoot,
                            my + inset,
                        ],
                        fill=color,
                        width=mark_w * 2,
                    )
                    cx += mark_w + group_gap
                else:
                    cx += stride
        else:
            # Too many — just show the number, centered
            label = f"x{self.count}"
            bbox = img.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            lx = mx0 + (avail_w - tw) // 2
            img.text((lx, my - 1), label, fill=color, font=font)

    def _deep_copy(self) -> "Shape":
        return StrobeShape(self.inner._deep_copy(), self.count, self.cfg, self.flash)


def render_animation(
    cfg: CartesianProductCfg,
    width: int = 640,
    height: int = 360,
    fps: int = 15,
    step_frames: int = 4,
    output_dir: str = "cachedir/cartesian",
) -> str:
    """Render the dimensional extrusion animation.

    Parameters
    ----------
    cfg : CartesianProductCfg
        Sweep configuration.
    width, height : int
        Video resolution.
    fps : int
        Frames per second.
    step_frames : int
        Frames to show each extrusion step (per sub-copy).
    output_dir : str
        Directory for the output video.

    Returns
    -------
    str
        Path to the output GIF file.
    """
    # Create cache key and check if animation already exists
    cache_key = _create_cache_key(cfg, width, height, fps, step_frames)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"cartesian_{cache_key}.png")

    # Return cached version if it exists
    if Path(out_path).exists():
        logger.info("Using cached animation: %s", out_path)
        return out_path

    logger.info("Rendering new animation: %s", out_path)
    dims = []
    for v in cfg.all_vars:
        real_vals = [val for val in v.values if val != GAP]
        n = len(real_vals)
        if n > 0:
            dims.append((v.name, n))

    if not dims:
        dims = [("x", 1)]

    logger.info("Generating animation: %d dimensions", len(dims))
    for name, size in dims:
        logger.info("  %s: %d values", name, size)

    font_large = _get_font(24)
    font_small = _get_font(14)

    frames: list[Image.Image] = []
    durations: list[int] = []  # per-frame duration in ms
    frame_duration_ms = 1000 // fps

    # Persistent text state — both lines always visible, no flickering
    current_dim_label = ""
    current_count_label = ""

    def make_frame(
        shape: Shape,
        dim_label: str | None = None,
        count_label: str | None = None,
        x_offset: int = 0,
    ):
        """Render one frame. Text is persistent — only updates when new values given.

        x_offset shifts the shape horizontally (positive = right). Parts that
        fall outside the canvas are clipped naturally by PIL.
        """
        nonlocal current_dim_label, current_count_label
        if dim_label is not None:
            current_dim_label = dim_label
        if count_label is not None:
            current_count_label = count_label

        img = Image.new("RGB", (width, height), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Reserve top 55px for text
        shape_area_top = 55
        sw, sh = shape.size()
        avail_w = width - 40
        avail_h = height - shape_area_top - 10
        scale = min(avail_w / max(sw, 1), avail_h / max(sh, 1), 1.0)

        if scale < 1.0:
            big = Image.new("RGB", (sw + 40, sh + 10), BG_COLOR)
            big_draw = ImageDraw.Draw(big)
            shape.draw(big_draw, 20, 5)
            new_w = int(big.width * scale)
            new_h = int(big.height * scale)
            big = big.resize((new_w, new_h), Image.Resampling.LANCZOS)
            paste_x = (width - big.width) // 2 + x_offset
            paste_y = shape_area_top + (avail_h - big.height) // 2
            img.paste(big, (paste_x, paste_y))
        else:
            sx = (width - sw) // 2 + x_offset
            sy = shape_area_top + (avail_h - sh) // 2
            shape.draw(draw, sx, sy)

        # Line 1: dimension name (always visible)
        if current_dim_label:
            bbox = draw.textbbox((0, 0), current_dim_label, font=font_large)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, 6), current_dim_label, fill=LABEL_COLOR, font=font_large)

        # Line 2: combination count (always visible, below dim name)
        if current_count_label:
            bbox = draw.textbbox((0, 0), current_count_label, font=font_small)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) // 2, 34), current_count_label, fill=(120, 120, 120), font=font_small
            )

        frames.append(img)
        durations.append(frame_duration_ms)

    # Minimum frames to hold each step so labels are readable (~0.5s)
    min_hold = max(1, fps // 2)

    def hold(n: int = 0):
        """Extend the last frame's duration instead of duplicating it."""
        durations[-1] += max(min_hold, n) * frame_duration_ms

    # Start with point
    shape = Shape()  # single cell
    make_frame(shape, count_label="1 point")
    hold()

    # Separate meta dims from spatial dims — each rendered distinctly
    spatial_dims = [(n, s) for n, s in dims if n not in ("over_time", "repeat")]
    repeat_dim = [(n, s) for n, s in dims if n == "repeat"]
    time_dim = [(n, s) for n, s in dims if n == "over_time"]

    logger.info(
        "Layout: %d spatial, %d repeat, %d over_time",
        len(spatial_dims),
        len(repeat_dim),
        len(time_dim),
    )

    # --- Phase 1: Extrude through each spatial dimension ---
    running_product = 1
    spatial_idx = 0
    dim_color = 0  # palette index, incremented per dimension
    for name, size in spatial_dims:
        if size <= 1:
            running_product *= size
            logger.info("Spatial dim %d: '%s' skipped (size=1)", spatial_idx, name)
            spatial_idx += 1
            dim_color += 1
            continue

        direction = _direction_for(spatial_idx)
        display_name = name.replace("_", " ")
        logger.info(
            "Spatial dim %d: '%s' (%d values, direction=%s)", spatial_idx, name, size, direction
        )

        make_frame(shape, dim_label=display_name)
        hold()

        old_shape = shape
        n_steps = size - 1  # k goes from 2..size
        for k in range(2, size + 1):
            shape = old_shape.extrude(k, direction, color_index=dim_color)
            make_frame(shape, count_label=f"{running_product * k} combinations")
            # Hold so total growth time ≈ step_frames regardless of element count
            n_extra = max(0, round(step_frames / n_steps) - 1)
            durations[-1] += n_extra * frame_duration_ms

        # shape is now the final extrusion (k == size) — no need to re-extrude
        running_product *= size

        make_frame(shape, count_label=f"{running_product} combinations")
        hold()
        spatial_idx += 1
        dim_color += 1

    # --- Phase 2: Repeat — strobe flash animation ---
    # Always shown (even ×1) to match the LaTeX summary.
    # Total repeat phase is hard-capped at ~3 seconds of frames.
    MAX_REPEAT_FRAMES = fps * 3
    if repeat_dim:
        repeat_size = repeat_dim[0][1]
        logger.info("Repeat: ×%d (strobe)", repeat_size)

        make_frame(shape, dim_label="repeat")
        hold()

        repeat_frame_count = 0
        for k in range(1, repeat_size + 1):
            if repeat_frame_count >= MAX_REPEAT_FRAMES:
                break
            flash_on = StrobeShape(shape, k, cfg, flash=1.0)
            make_frame(flash_on, count_label=f"{running_product} x {k} repeats")
            make_frame(StrobeShape(shape, k, cfg, flash=0.0))
            repeat_frame_count += 2
        shape = StrobeShape(shape, repeat_size, cfg, flash=0.0)
        running_product *= repeat_size

        make_frame(shape, count_label=f"{running_product} combinations")
        hold()
        spatial_idx += 1
        dim_color += 1

    # --- Phase 3: over_time as film strip that slides in from the right ---
    # Always shown (even ×1) to match the LaTeX summary.
    if time_dim:
        time_size = time_dim[0][1]
        running_product *= time_size
        logger.info("Over time: %d steps (film strip slide-in)", time_size)

        make_frame(shape, dim_label="over time")
        hold()

        timeline_shape = TimelineShape(shape, time_size)
        count_text = f"{running_product} combinations x ({time_size} times)"

        # Slide the film strip in from the right with ease-out deceleration
        slide_n = max(4, fps // 2)  # ~0.5s of sliding
        for f in range(slide_n):
            t = f / max(slide_n - 1, 1)  # 0 → 1
            ease = 1 - (1 - t) ** 3  # cubic ease-out
            offset = int(width * (1 - ease))  # width → 0
            make_frame(timeline_shape, count_label=count_text, x_offset=offset)

        hold()  # settled at center
        shape = timeline_shape

    # Final hold
    make_frame(shape, count_label=f"{running_product} total combinations")
    durations[-1] += fps * frame_duration_ms  # 1 second hold

    # Write animation — APNG is ~12x faster than GIF to encode
    frames[0].save(
        out_path,
        format="PNG",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,  # loop forever
    )

    logger.info("Saved %d frames to %s", len(frames), out_path)
    return out_path
