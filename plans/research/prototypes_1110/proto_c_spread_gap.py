"""Prototype C for ticket #1110: the Spread(mean_std) gap.

A6 §3 declares Spread(mean_std) a rerun gap: rerun has no filled-band view, so
the fallback is three SeriesLines (mean, mean+std, mean-std). This prototype:

1. builds a real rerun recording with the three-lines fallback, styled so the
   band edges are visually subordinate to the mean (thin lines, same hue), on
   data shaped like bencher's CurveResult output (sin curve, noisy repeats);
2. renders a side-by-side matplotlib mock — filled band (what hv.Spread gives
   today) vs the three-lines fallback with the same styling as the recording —
   so the legibility difference can be judged from a PNG.

Run:  pixi run python plans/research/prototypes_1110/proto_c_spread_gap.py
Then: rerun plans/research/prototypes_1110/out/spread_fallback.rrd
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


def make_data():
    theta = np.linspace(0, np.pi, 30)
    mean = np.sin(theta)
    std = 0.05 + 0.15 * np.abs(np.cos(theta))  # varying width, like real repeats
    return theta, mean, std


def build_recording() -> Path:
    import rerun as rr

    theta, mean, std = make_data()
    rrd = OUT / "spread_fallback.rrd"
    rr.init("bencher_1110_spread_fallback")
    rr.save(str(rrd))

    # Static styling logged once per entity; SeriesLines styles the plot.
    base = [31, 119, 180]  # matplotlib C0 blue
    rr.log(
        "curve/out_sin/mean",
        rr.SeriesLines(colors=[base], widths=[2.5], names=["out_sin (mean)"]),
        static=True,
    )
    for edge in ("upper", "lower"):
        rr.log(
            f"curve/out_sin/{edge}",
            rr.SeriesLines(
                colors=[[130, 180, 210]],  # lighter same-hue
                widths=[0.75],
                names=[f"out_sin {'+' if edge == 'upper' else '-'}1σ"],
            ),
            static=True,
        )

    for i, t in enumerate(theta):
        rr.set_time("theta", sequence=i)  # rerun timelines index the x axis
        rr.log("curve/out_sin/mean", rr.Scalars(mean[i]))
        rr.log("curve/out_sin/upper", rr.Scalars(mean[i] + std[i]))
        rr.log("curve/out_sin/lower", rr.Scalars(mean[i] - std[i]))
    rr.disconnect()
    print(f"recording written: {rrd} ({rrd.stat().st_size} bytes)")
    print("three sibling entities under curve/out_sin/ -> one TimeSeriesView shows all three")
    return rrd


def build_visual_mock() -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    theta, mean, std = make_data()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)

    ax = axes[0]
    ax.plot(theta, mean, color="#1f77b4", lw=2.5, label="out_sin (mean)")
    ax.fill_between(theta, mean - std, mean + std, color="#1f77b4", alpha=0.25, label="±1σ band")
    ax.set_title("today: hv.Spread filled band")

    ax = axes[1]
    ax.plot(theta, mean, color="#1f77b4", lw=2.5, label="out_sin (mean)")
    ax.plot(theta, mean + std, color="#82b4d2", lw=0.75, label="+1σ")
    ax.plot(theta, mean - std, color="#82b4d2", lw=0.75, label="-1σ")
    ax.set_title("rerun fallback: three SeriesLines")

    for ax in axes:
        ax.set_xlabel("theta [rad]")
        ax.legend(loc="lower center", fontsize=8)
    axes[0].set_ylabel("out_sin [v]")
    png = OUT / "spread_band_vs_three_lines.png"
    fig.savefig(png, dpi=110, bbox_inches="tight")
    print(f"visual mock written: {png}")
    return png


if __name__ == "__main__":
    build_recording()
    build_visual_mock()
