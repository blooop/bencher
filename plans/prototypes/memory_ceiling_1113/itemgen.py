"""Synthetic report-scale ``.rrd`` item generator for issue #1113.

Each *item* mimics one ``ResultRerun`` artifact produced by a benchmark sample:
user code logging at arbitrary, self-chosen entity paths (``series/metric``,
``camera/rgb``, ``tensor/activations``) with NO item prefix -- exactly the
recordings that already exist on disk today.

Per-item content (defaults):
- 500 scalar steps on a ``step`` sequence timeline (``rr.Scalars``)
- 8 raw 512x512x3 uint8 random images (``rr.Image``, incompressible)
- one static 64^3 float32 random tensor (``rr.Tensor``)

That is ~7.3 MB on disk per item, so 24 items make a ~175 MB report input.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def log_item(
    rec,
    prefix: str,
    seed: int,
    *,
    steps: int = 500,
    images: int = 8,
    size: int = 512,
    tensor: int = 64,
) -> None:
    """Log one item's data into ``rec`` under ``prefix`` ('' = user-chosen paths)."""
    import rerun as rr

    rng = np.random.default_rng(seed)
    p = prefix.rstrip("/") + "/" if prefix else ""
    for step in range(steps):
        rec.set_time("step", sequence=step)
        rec.log(f"{p}series/metric", rr.Scalars(float(np.sin(step * 0.1) + seed)))
    stride = max(1, steps // max(images, 1))
    for i in range(images):
        rec.set_time("step", sequence=i * stride)
        rec.log(f"{p}camera/rgb", rr.Image(rng.integers(0, 256, (size, size, 3), dtype=np.uint8)))
    rec.log(
        f"{p}tensor/activations",
        rr.Tensor(rng.standard_normal((tensor, tensor, tensor)).astype(np.float32)),
        static=True,
    )


def generate_items(outdir: Path, n_items: int, **cfg) -> list[Path]:
    """Write ``n_items`` standalone item recordings to ``outdir`` and return their paths."""
    import rerun as rr

    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n_items):
        path = outdir / f"item_{i:03d}.rrd"
        if not path.is_file():
            rec = rr.RecordingStream("bencher_item", make_default=False, make_thread_default=False)
            rec.save(str(path))
            log_item(rec, "", i, **cfg)
            rec.flush()
            rec.disconnect()
        paths.append(path)
    return paths
