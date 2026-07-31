"""Surfacing for render failures that must not silently shrink a report.

A plot that raises used to be recorded with ``logger.exception`` and nothing
else.  Loggers are off by default in library use, so the report was written
*missing whole plots* while every caller-visible signal still said success: no
warning, a zero exit code, and an HTML file that looks complete unless you
already know which plot should have been there.

Every failure now leaves two marks instead of one:

* a :mod:`warnings` warning, so an embedding test runner (pytest's warnings
  summary, ``-W error``) sees it without configuring logging;
* a visible pane in the report itself, so the gap is legible to whoever opens
  the HTML rather than only to whoever re-runs it.

The logger call is kept for callers that already capture it.
"""

from __future__ import annotations

import logging
import traceback
import warnings

import panel as pn

logger = logging.getLogger(__name__)


class RenderFailedWarning(UserWarning):
    """A plot could not be rendered; the report is missing it."""


def report_render_failure(what: str, exc: BaseException) -> pn.pane.Markdown:
    """Log, warn about, and build a visible pane for a failed render of *what*.

    Returns the pane to append in place of the plot that failed, so a caller can
    keep rendering the rest of the report.

    The traceback comes from *exc* rather than from the ambient
    ``sys.exc_info()``, so a caller that has already left its ``except`` block
    (or never had one) still gets the real traceback in the log instead of
    ``NoneType: None``.
    """
    logger.error("%s failed", what, exc_info=exc)
    warnings.warn(
        f"{what} failed to render ({type(exc).__name__}: {exc}); the report is missing this plot",
        RenderFailedWarning,
        stacklevel=3,
    )
    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return pn.pane.Markdown(
        f"### ⚠️ {what} failed to render\n\n"
        f"```\n{detail}\n```\n\n"
        "The rest of this report rendered normally. This pane marks a plot that "
        "is missing, so an incomplete report cannot be mistaken for a complete one.",
        name=f"{what} (failed)",
    )
