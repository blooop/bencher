"""Configuration for the benchmark health scorecard.

The scorecard machinery is generic; everything project-specific — how tags map
to a category and display name, which metric names are synonyms, which values
are fractions to show as percentages, and where reports live on disk — is
supplied here so one renderer serves any project. Every field has a default, so
the zero-config path still produces a page (auto-named benchmarks, no aliases).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

# Sentinel category for unregistered tags; sorts last in the display order.
DEFAULT_OTHER_CATEGORY = "Other"


@dataclass(frozen=True)
class ReportLayout:
    """Where per-benchmark artifacts live under the reports directory.

    ``root`` is the subdirectory holding one folder per benchmark tag (``""``
    means the reports directory itself). ``link_pattern`` builds the relative
    href to a benchmark's HTML report; ``{root}``, ``{tag}`` and ``{bench_name}``
    are substituted.
    """

    root: str = ""
    link_pattern: str = "{root}/{tag}/{bench_name}.html"

    def link(self, tag: str, bench_name: str) -> str:
        rendered = self.link_pattern.format(root=self.root, tag=tag, bench_name=bench_name)
        return rendered.lstrip("/")


@dataclass(frozen=True)
class ScorecardConfig:
    """Project-specific inputs to the scorecard renderer.

    Args:
        registry: ``tag -> (category, display_name, description)`` for known
            benchmarks. Unregistered tags fall back to an auto-generated name in
            :attr:`other_category`.
        aliases: ``raw_metric_name -> canonical_name`` so equivalent metrics from
            different benchmarks share one column.
        percent_metrics: metric names whose value is a ``0..1`` fraction to be
            rendered as a percentage rather than a bare number.
        secondary_metrics: metric names describing the *run* rather than what it
            measured (harness lifecycle, artifact capture). Every benchmark
            reports them, so in the main table they crowd out the columns a
            section is about; they render in a collapsed group beneath it.
        secondary_label: heading for that group.
        layout: on-disk report layout (see :class:`ReportLayout`).
        other_category: fallback category for unregistered tags.
    """

    registry: Mapping[str, tuple[str, str, str]] = field(default_factory=dict)
    aliases: Mapping[str, str] = field(default_factory=dict)
    percent_metrics: frozenset[str] = frozenset()
    secondary_metrics: frozenset[str] = frozenset()
    secondary_label: str = "Harness health"
    layout: ReportLayout = field(default_factory=ReportLayout)
    other_category: str = DEFAULT_OTHER_CATEGORY

    def category_order(self) -> list[str]:
        """Category display order: first-appearance in the registry, Other last."""
        order: list[str] = []
        for category, _name, _description in self.registry.values():
            if category not in order:
                order.append(category)
        if self.other_category not in order:
            order.append(self.other_category)
        return order


@dataclass(frozen=True)
class Chrome:
    """Optional page header content (title, provenance, and CI nav links).

    Every field is optional; each nav link renders only when supplied, so the
    default template carries CI-flavored links harmlessly for callers that leave
    them blank.
    """

    title: str = "Benchmark Health Scorecard"
    commit_sha: str = ""
    branch: str = ""
    pr_number: str = ""
    run_url: str = ""
    repo_url: str = ""
    nightly_url: str = ""
    main_url: str = ""
    stable_url: str = ""
