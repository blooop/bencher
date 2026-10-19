"""The evidence example writes a Markdown block that judges the declared claim."""

from __future__ import annotations

from bencher.example.example_evidence import example_evidence


def test_example_shows_the_baseline_failing_and_the_candidate_holding(tmp_path):
    files = example_evidence(tmp_path)
    md = files.markdown_path.read_text(encoding="utf-8")
    assert "xychart-beta" in md
    assert "baseline fails (worst 0.9 at speed=3" in md
    assert "candidate holds (worst 0.6 at speed=3" in md
    assert files.pngs["stop_distance"].exists()
