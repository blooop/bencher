"""Example: before/after evidence for a pull request, with a declared claim.

A change is meant to bring stop distance under 0.7 m at every speed. The example
collects the metric twice -- once with the old controller gain, once with the new
one -- and writes what ``bencher compare --markdown --png`` writes: a Markdown block
to paste as a PR's ``## Evidence`` section (a Mermaid chart and a caption per
metric) and a PNG per metric with the claim drawn on it.

In a real PR the two results come from two revisions of the code, and
``bencher ab -- python my_bench.py`` collects both for you::

    python -m bencher.example.example_evidence            # temp dir
    python -m bencher.example.example_evidence /tmp/out    # or a directory you pick
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import bencher as bn


class Braking(bn.ParametrizedSweep):
    """Stop distance of a braking controller; the claim is the change's goal."""

    speed = bn.FloatSweep(default=1.0, bounds=(0.5, 3.0), samples=6, units="m/s")
    gain = bn.FloatSweep(default=0.3, bounds=(0.1, 0.5), doc="Controller gain under test")

    stop_distance = bn.ResultFloat(units="m", claim="< 0.7")

    def benchmark(self):
        self.stop_distance = self.gain * self.speed


def _collect(gain: float) -> bn.BenchResult:
    bench = bn.Bench("braking", Braking())
    result = bench.collect(
        input_vars=["speed"],
        result_vars=["stop_distance"],
        const_vars=[("gain", gain)],
        run_cfg=bn.BenchRunCfg(repeats=2),
    )
    bench.close()
    return result


def example_evidence(out_dir: str | Path | None = None) -> bn.EvidenceFiles:
    """Collect before (gain 0.3) and after (gain 0.2), then write the evidence."""
    out_dir = Path(out_dir) if out_dir is not None else Path(tempfile.mkdtemp())
    files = bn.write_evidence(
        _collect(gain=0.3),
        _collect(gain=0.2),
        json_path=out_dir / "comparison.json",
        markdown_path=out_dir / "evidence.md",
        png_dir=out_dir,
    )
    print(files.markdown_path.read_text(encoding="utf-8"))
    return files


if __name__ == "__main__":
    example_evidence(sys.argv[1] if len(sys.argv) > 1 else None)
