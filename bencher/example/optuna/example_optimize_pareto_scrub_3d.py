"""Scrub a three-objective Pareto front, with the front itself in a 3-D view.

Two objectives make a trade you can draw flat: one axis against the other, and the
front is a curve. Three do not. Any one plane through a three-objective front hides
a whole direction of the trade, and which pair you happen to plot decides which
designs look good -- so the front is put in a rerun 3-D view instead, where the
reader can turn it and see the surface the designs actually lie on.

Everything else is the two-objective scrub: ``bench.plot_pareto_front`` lays the
front out as a sweep over ``pareto_rank``, one design per tick, the whole worker
re-run at each so its media is there. Under ``backend="rerun"`` the slider walks the
front while the cube beneath it says where along the trade the cursor is parked.

The design here is a heat sink: how tall the fins are and how tightly they are
packed. Taller, denser fins move more heat -- and cost more metal, and choke the
airflow. No design wins on all three.
"""

from PIL import Image, ImageDraw

import bencher as bn


class HeatSink(bn.ParametrizedSweep):
    """A finned heat sink: thermal resistance against pressure drop against cost."""

    fin_height = bn.FloatSweep(default=20.0, bounds=[8.0, 40.0], units="mm")
    fin_pitch = bn.FloatSweep(default=4.0, bounds=[1.5, 8.0], units="mm")

    resistance = bn.ResultFloat(units="K/W", direction=bn.OptDir.minimize)
    pressure_drop = bn.ResultFloat(units="Pa", direction=bn.OptDir.minimize)
    material = bn.ResultFloat(units="cm^3", direction=bn.OptDir.minimize)
    profile = bn.ResultImage()

    _WIDTH_MM = 60.0
    _DEPTH_MM = 40.0
    _THICKNESS_MM = 1.0

    def _fin_count(self) -> int:
        return max(2, int(self._WIDTH_MM // self.fin_pitch))

    def benchmark(self):
        fins = self._fin_count()
        # Surface area carries the heat away, so resistance falls as it grows.
        area = fins * 2.0 * self.fin_height * self._DEPTH_MM
        self.resistance = float(120.0 / area + 0.02)
        # A tighter channel between taller fins costs more to push air through.
        gap = max(self.fin_pitch - self._THICKNESS_MM, 0.2)
        self.pressure_drop = float(4.0 * self.fin_height / gap**1.6)
        self.material = float(fins * self.fin_height * self._DEPTH_MM * self._THICKNESS_MM / 1000.0)
        self.profile = self._draw(fins)

    def _draw(self, fins: int) -> str:
        """The sink's cross-section, which is the half a scatter cannot show."""
        width, height = 320, 200
        scale = width / (self._WIDTH_MM * 1.2)
        image = Image.new("RGB", (width, height), (18, 20, 26))
        draw = ImageDraw.Draw(image)
        base_y = height - 30
        draw.rectangle(
            [(20, base_y), (20 + self._WIDTH_MM * scale, base_y + 12)], fill=(90, 100, 120)
        )
        for index in range(fins):
            x = 20 + index * self.fin_pitch * scale
            draw.rectangle(
                [
                    (x, base_y - self.fin_height * scale * 2.2),
                    (x + self._THICKNESS_MM * scale, base_y),
                ],
                fill=(120, 210, 255),
            )
        path = bn.gen_image_path("heatsink")
        image.save(path, "PNG")
        return str(path)


def example_optimize_pareto_scrub_3d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Search three objectives, then walk the front with a slider and a 3-D view."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=1)
    bench = HeatSink().to_bench(run_cfg)

    result = bench.optimize(
        title="Heat, back-pressure and metal",
        input_vars=["fin_height", "fin_pitch"],
        result_vars=["resistance", "pressure_drop", "material"],
        n_trials=60,
        warm_start=False,
        plot=False,
    )
    front = result.pareto_trials()
    bench.report.append_markdown(
        f"### The front\n\n{len(front)} designs of {len(result.study.trials)} trials are "
        "Pareto optimal across all three objectives. There is no plane that shows that "
        "honestly -- plot any two and the third goes missing, and the designs that look "
        "best are the ones the hidden axis was about to rule out. So the front is drawn "
        "as points in a space you can turn."
    )

    # One viewer: the slider walks the front, the cube says where on it the cursor is.
    bench.run_cfg.backend = "rerun"
    bench.plot_pareto_front(
        result,
        description=(
            "Each tick is one design on the front, lowest thermal resistance first. "
            "The cube beneath is the front in the space it was ranked in -- drag to "
            "turn it -- with the cursor's own design picked out and labelled."
        ),
    )
    return bench


if __name__ == "__main__":
    bn.run(example_optimize_pareto_scrub_3d)
