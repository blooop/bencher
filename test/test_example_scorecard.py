"""Tests for the scorecard example (bencher.example.example_scorecard)."""

from __future__ import annotations

from pathlib import Path

from bencher.example.example_scorecard import example_scorecard


def test_example_renders_page(tmp_path: Path):
    out = example_scorecard(tmp_path)
    assert out == tmp_path / "index.html"
    assert out.exists()


def test_example_covers_all_verdicts(tmp_path: Path):
    html = example_scorecard(tmp_path).read_text()
    for verdict in ("v-regressed", "v-improved", "v-passed", "v-trend"):
        assert verdict in html


def test_example_covers_distribution_archetypes(tmp_path: Path):
    html = example_scorecard(tmp_path).read_text()
    for name in (
        "Rock Solid",
        "High Noise",
        "Very Noisy",
        "Improving",
        "Regressing",
        "Ungated Trend",
        "Step Change",
        "Converging Noise",
        "Expanding Noise",
        "Sawtooth Flip",
        "Outlier Spike",
        "First Run",
    ):
        assert name in html
    # One shared "value" column => one sparkline per archetype, all comparable.
    assert html.count("<svg") >= 12


def test_example_exercises_config_options(tmp_path: Path):
    html = example_scorecard(tmp_path).read_text()
    # aliases: wall_time -> duration column, raw name surfaced in the tooltip
    assert "variable: wall_time" in html
    # percent_metrics: completion rendered as a percentage
    assert "%" in html
    # chrome: title + PR badge
    assert "Benchmark Health Scorecard — Example" in html
    assert "PR #123" in html
    # metric-less report reachable via the link section
    assert "Reports without metrics" in html
    assert "Render Gallery" in html


def test_example_is_deterministic(tmp_path: Path):
    a = example_scorecard(tmp_path / "a").read_text()
    b = example_scorecard(tmp_path / "b").read_text()
    # Only the generated-at timestamp differs between runs; strip it before diffing.
    import re

    def strip(h: str) -> str:
        return re.sub(r"\d{4}-\d\d-\d\d \d\d:\d\d UTC", "", h)

    assert strip(a) == strip(b)
