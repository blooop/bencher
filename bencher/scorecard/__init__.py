"""Generic benchmark health scorecard: summaries -> one grouped HTML page.

Reads the machine-readable ``*.summary.json`` written by
:func:`~bencher.report_export.result_to_json` (with ``include_series=True``) for
a set of benchmarks and renders a single page where every scalar metric shows,
at a glance, a regression verdict and a noise sparkline. Project specifics — the
tag registry, metric aliases, and report layout — are supplied via
:class:`ScorecardConfig`.
"""

from bencher.scorecard.config import (
    DEFAULT_OTHER_CATEGORY,
    Chrome,
    ReportLayout,
    ScorecardConfig,
)
from bencher.scorecard.discover import (
    discover_report_links,
    discover_summaries,
    tag_to_name,
)
from bencher.scorecard.model import (
    build_cell,
    cell_verdict,
    fmt_change,
    fmt_value,
    metric_columns,
    unify_metric_names,
)
from bencher.scorecard.render import generate_scorecard

__all__ = [
    "DEFAULT_OTHER_CATEGORY",
    "Chrome",
    "ReportLayout",
    "ScorecardConfig",
    "build_cell",
    "cell_verdict",
    "discover_report_links",
    "discover_summaries",
    "fmt_change",
    "fmt_value",
    "generate_scorecard",
    "metric_columns",
    "tag_to_name",
    "unify_metric_names",
]
