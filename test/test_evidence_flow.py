"""The motion rule of the evidence graphics' SVGs, checked on a written gallery.

Only ``stroke-dashoffset`` animates, by CSS, on a dashed stroke with no fill; every
animated element is a median connector, a forest connector or a changed-run outline,
and carries the ``.fl`` class that ``prefers-reduced-motion`` stops. No SMIL, no
transition, and no interval mark is left in any chart.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import numpy as np
import pytest

from bencher import infographic as ig
from bencher.evidence_report import report_from_rows
from bencher.example import example_evidence_gallery as gallery

if TYPE_CHECKING:
    from pathlib import Path

SMIL = {"animate", "animateTransform", "animateMotion", "set", "animateColor"}
STROKED = {"line", "path", "rect", "polyline"}
KEYFRAMES = re.compile(r"@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}")
REDUCED = "@media (prefers-reduced-motion:reduce){.fl{animation:none!important}}"


def _tag(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1]


def _decls(body: str) -> dict[str, str]:
    return {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in body.split(";") if ":" in d)}


def check_motion(path: Path) -> tuple[dict[str, int], list[str]]:
    """Return (flowing elements per kind, errors) for one SVG."""
    errs: list[str] = []
    root = ET.parse(path).getroot()  # noqa: S314 - our own generated files
    css = "".join(s.text or "" for s in root.iter() if _tag(s) == "style")
    if "transition" in css:
        errs.append("css has a transition")
    keyframes = {}
    for m in KEYFRAMES.finditer(css):
        keyframes[m.group(1)] = m.group(2)
        props = {k for blk in re.findall(r"\{([^{}]*)\}", m.group(2)) for k in _decls(blk)}
        if props != {"stroke-dashoffset"}:
            errs.append(f"@keyframes {m.group(1)} animates {sorted(props)}")
    rest = KEYFRAMES.sub("", css)
    if keyframes and REDUCED not in rest:
        errs.append("no prefers-reduced-motion rule that stops .fl")
    rest = rest.replace(REDUCED, "")
    animated: set[str] = set()
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", rest):
        sel, decls = m.group(1).strip(), _decls(m.group(2))
        if not any(k.startswith("animation") for k in decls):
            continue
        if not re.fullmatch(r"\.[\w-]+", sel):
            errs.append(f"animation on a selector that is not one class: {sel}")
            continue
        if "stroke-dasharray" not in decls:
            errs.append(f"{sel} animates without stroke-dasharray")
        if decls.get("animation", "").split()[0] not in keyframes:
            errs.append(f"{sel} uses unknown keyframes")
        animated.add(sel[1:])
    if animated - {"fl"}:
        errs.append(f"classes other than .fl animate: {sorted(animated)}")
    counts = dict.fromkeys(ig.FLOW_KINDS, 0)
    for e in root.iter():
        tag = _tag(e)
        if tag in SMIL:
            errs.append(f"SMIL element <{tag}>")
        style = e.attrib.get("style", "")
        if "anim" in style:
            errs.append(f"inline animation style on <{tag}>")
        classes = set(e.attrib.get("class", "").split())
        if not classes & animated:
            continue
        kinds = [k for k in ig.FLOW_KINDS if k in classes]
        if len(kinds) != 1:
            errs.append(f"<{tag} class={e.attrib['class']!r}> flows but is not a salient line")
            continue
        counts[kinds[0]] += 1
        if tag not in STROKED:
            errs.append(f"<{tag}> animates but is not a stroked line")
        if "fill: none" not in style:
            errs.append(f"<{tag} class={e.attrib['class']!r}> animates and has a fill")
        if "stroke-dash" in style:
            errs.append(f"<{tag}> keeps an inline dash that would beat the class")
    return counts, errs


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    out = tmp_path_factory.mktemp("flow")
    reports = {}
    for slug in ("improvement", "forest", "success-rate", "sweep-1d", "inconclusive"):
        base, cand, opts = gallery.SCENARIOS[slug][1](np.random.default_rng(gallery.SEED))
        reports[slug] = report_from_rows(base, cand, out / slug, **opts)
    return reports


def test_every_svg_keeps_the_motion_rule(written: dict) -> None:
    totals = dict.fromkeys(ig.FLOW_KINDS, 0)
    bad = {}
    svgs = [p for r in written.values() for p in r.files.values() if p.suffix == ".svg"]
    assert svgs
    for path in svgs:
        counts, errs = check_motion(path)
        if errs:
            bad[path.name] = errs
        for k, v in counts.items():
            totals[k] += v
    assert not bad
    # Each kind of salient line flows somewhere in the gallery.
    assert all(totals.values()), totals


def test_moved_panels_flow_and_still_ones_do_not(written: dict) -> None:
    # improvement: one ▲ and one ▼ tile, each with a flowing median connector.
    card = written["improvement"].files["scorecard-light.svg"]
    assert check_motion(card)[0]["medflow"] == 2
    # inconclusive: the ? connector is drawn but still, so nothing flows.
    still = written["inconclusive"].files["scorecard-light.svg"]
    assert 'class="fl' not in still.read_text(encoding="utf-8")
    # forest: 2 ▲ + 2 ▼ rows flow from 0; the ? row and the ≈ rows do not.
    forest = written["forest"].files["forest-dark.svg"]
    assert check_motion(forest)[0]["estflow"] == 4


def test_no_interval_mark_and_png_stays_still(written: dict) -> None:
    for r in written.values():
        for path in r.files.values():
            if path.suffix == ".svg":
                text = path.read_text(encoding="utf-8").lower()
                assert "likely range" not in text
                assert "whisker" not in text
    md = written["improvement"].markdown
    assert "whisker" not in md
    assert "90 % CI:" in written["forest"].markdown


def test_markdown_links_svg_by_default_and_png_on_request(written: dict) -> None:
    report = written["improvement"]
    assert 'srcset="scorecard-dark.svg"' in report.markdown
    assert "Data: [evidence-data.csv]" in report.markdown
    md = report.render(svg=False)
    assert 'srcset="scorecard-dark.svg"' not in md
    assert 'srcset="scorecard-dark.png"' in md
    assert 'src="scorecard-light.png"' in md
    report.render(svg=True)


def test_animate_flows_leaves_untagged_svg_alone() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><path style="fill: none"/></svg>'
    assert ig.animate_flows(svg) == svg
