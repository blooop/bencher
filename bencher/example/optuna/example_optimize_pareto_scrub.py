"""Scrub a Pareto front: every design on it, drawn, under one slider.

A two-objective study has no single answer. Optuna draws its front as a scatter,
which says what each design *scored* and nothing about what each design *is* --
for a design whose worth is a shape, a layout, a picture, that is the half that
decides it.

``bench.plot_pareto_front`` lays the front out as a sweep over ``pareto_rank``:
the front ordered along one objective, best first, one sample per design, with
the whole worker re-run at each so every result var it produces is there. Under
``backend="rerun"`` that sweep becomes one viewer whose cursor walks the front,
and the read-out under it names the design the cursor is parked on.

Here the design is an antenna array: how far apart the elements sit, and how
sharply the aperture is tapered. Wide spacing buys a narrow main beam and pays
for it in side lobes, so no design wins on both.
"""

import math

import numpy as np
from PIL import Image, ImageDraw

import bencher as bn


class ArrayDesign(bn.ParametrizedSweep):
    """An 8-element antenna array: beam width against side-lobe level."""

    spacing = bn.FloatSweep(default=0.5, bounds=[0.3, 1.2], units="wavelengths")
    taper = bn.FloatSweep(default=0.0, bounds=[0.0, 6.0], units="dB")
    steer = bn.StringSweep(["broadside", "off_axis"], doc="Where the beam is pointed")

    beam_width = bn.ResultFloat(units="deg", direction=bn.OptDir.minimize)
    side_lobe = bn.ResultFloat(units="dB", direction=bn.OptDir.minimize)
    pattern = bn.ResultImage()

    _ELEMENTS = 8

    def _weights(self) -> np.ndarray:
        """Element amplitudes: a raised cosine the taper deepens."""
        positions = np.linspace(-1.0, 1.0, self._ELEMENTS)
        depth = 1.0 - 10.0 ** (-self.taper / 20.0)
        return 1.0 - depth * (1.0 - np.cos(np.pi * positions / 2.0))

    def _response(self) -> tuple[np.ndarray, np.ndarray]:
        """Array response in dB, against angle in degrees."""
        angles = np.linspace(-90.0, 90.0, 361)
        offset = 0.0 if self.steer == "broadside" else math.radians(20.0)
        phase = (
            2.0
            * np.pi
            * self.spacing
            * np.arange(self._ELEMENTS)[:, None]
            * (np.sin(np.radians(angles))[None, :] - math.sin(offset))
        )
        field = np.abs((self._weights()[:, None] * np.exp(1j * phase)).sum(axis=0))
        return angles, 20.0 * np.log10(np.maximum(field / field.max(), 1e-6))

    def benchmark(self):
        angles, response = self._response()
        peak = int(np.argmax(response))
        # Half-power width: how far either side of the peak the response holds -3 dB.
        above = np.flatnonzero(response >= -3.0)
        self.beam_width = float(angles[above[-1]] - angles[above[0]])
        # The tallest lobe outside the main one, which is what a taper buys.
        outside = np.abs(angles - angles[peak]) > max(self.beam_width, 1.0)
        self.side_lobe = float(response[outside].max()) if outside.any() else -60.0
        self.pattern = self._draw(angles, response)

    def _draw(self, angles: np.ndarray, response: np.ndarray) -> str:
        """The pattern as a picture, which is the half a scatter plot cannot show."""
        width, height = 320, 200
        image = Image.new("RGB", (width, height), (18, 20, 26))
        draw = ImageDraw.Draw(image)
        for level in (-3, -13, -30):
            y = height * (1.0 - (level + 60.0) / 60.0)
            draw.line([(0, y), (width, y)], fill=(48, 52, 62))
        points = [
            (
                width * (angle + 90.0) / 180.0,
                height * (1.0 - (max(value, -60.0) + 60.0) / 60.0),
            )
            for angle, value in zip(angles, response, strict=True)
        ]
        draw.line(points, fill=(120, 210, 255), width=2)
        path = bn.gen_image_path("pattern")
        image.save(path, "PNG")
        return str(path)


def example_optimize_pareto_scrub(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Search two objectives, then walk the front with a slider."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=1)
    bench = ArrayDesign().to_bench(run_cfg)

    # `steer` is a condition the design is judged under, not a design choice, so it
    # is aggregated inside each trial: a trial is one array scored at both pointings.
    result = bench.optimize(
        title="Beam width against side lobes",
        input_vars=["spacing", "taper", "steer"],
        result_vars=["beam_width", "side_lobe"],
        n_trials=40,
        aggregate=["steer"],
        agg_fn="max",
        warm_start=False,
        plot=False,
    )
    bench.report.append_markdown(
        f"### The front\n\n{len(result.pareto_trials())} designs of "
        f"{len(result.study.trials)} trials are Pareto optimal. "
        "Neither objective can be improved on any of them without giving up the other, "
        "so the choice between them is a judgement, and it wants the patterns on screen."
    )

    # One viewer, one slider, every design on the front drawn at both pointings.
    bench.run_cfg.backend = "rerun"
    bench.plot_pareto_front(
        result,
        description=(
            "Each tick is one design on the Pareto front, narrowest beam first. "
            "The read-out under the views names its spacing and taper and the scores "
            "it was ranked on; the two views are the pointings it was judged across."
        ),
    )
    return bench


if __name__ == "__main__":
    bn.run(example_optimize_pareto_scrub)
