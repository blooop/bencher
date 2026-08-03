"""The ``rerun``-gated names on the ``bencher`` package are always present.

Seven exports (``capture_rerun_rrd``, ``capture_rerun_window``, ``rerun_to_pane``,
``RerunResult``, ``ComposableContainerRerun``, ``RerunRecording``, ``RerunViewKind``,
``RerunSummaryResult``) used to be bound only inside ``try``/``except
ModuleNotFoundError`` in ``bencher/__init__.py``. On an install without ``rerun-sdk``
they simply did not exist, so ``bn.capture_rerun_rrd`` raised ``AttributeError: module
'bencher' has no attribute ...`` -- a message naming neither the optional dependency nor
how to install it -- and ``bencher``'s public surface was *partially defined*, which is
what ty reports as ``possibly-missing-attribute`` (plan 23 P12b).

The except branch cannot be exercised in an environment that has ``rerun-sdk``
installed, which this one does; these tests therefore drive ``_requires_rerun``
directly. Without them the branch is untested code that only runs on the installs
least able to report a problem.
"""

from __future__ import annotations

import pytest

import bencher as bn
from bencher import _requires_rerun

# Every name bound in one of the three rerun-gated try/except blocks.
RERUN_EXPORTS = [
    "capture_rerun_rrd",
    "capture_rerun_window",
    "rerun_to_pane",
    "RerunResult",
    "ComposableContainerRerun",
    "RerunRecording",
    "RerunViewKind",
    "RerunSummaryResult",
]


@pytest.mark.parametrize("name", RERUN_EXPORTS)
def test_export_exists_regardless_of_the_extra(name: str) -> None:
    """The attribute is defined on both branches, so no caller has to probe for it."""
    assert hasattr(bn, name), (
        f"bencher.{name} is not defined. Every rerun-gated export must be bound on "
        "both branches of its try/except so the public surface is total."
    )


def test_placeholder_names_the_missing_dependency() -> None:
    """Using a placeholder says what to install, rather than 'has no attribute'."""
    placeholder = _requires_rerun("capture_rerun_rrd")
    with pytest.raises(ImportError) as ctx:
        placeholder()
    message = str(ctx.value)
    assert "bencher.capture_rerun_rrd" in message
    assert "rerun-sdk" in message
    assert "pip install rerun-sdk" in message


def test_placeholder_raises_on_any_call_signature() -> None:
    """The real exports take varied arguments; the placeholder must not shadow the
    ImportError with a TypeError about the arguments."""
    placeholder = _requires_rerun("capture_rerun_window")
    with pytest.raises(ImportError):
        placeholder(600, height=600)


def test_placeholder_is_a_class_so_isinstance_stays_legal() -> None:
    """Returned as a class, not a function: code doing ``isinstance(x, bn.RerunRecording)``
    on an install without the extra gets False, not ``TypeError: isinstance() arg 2 must
    be a type``."""
    placeholder = _requires_rerun("RerunRecording")
    assert isinstance(placeholder, type)
    assert not isinstance(object(), placeholder)


def test_placeholder_attribute_access_also_names_the_dependency() -> None:
    """``RerunViewKind`` is an enum -- read as a namespace, never called. Attribute
    access must reach the same ImportError, not ``AttributeError: type object ... has no
    attribute 'spatial_2d'``, which is the failure the placeholder exists to replace."""
    placeholder = _requires_rerun("RerunViewKind")
    with pytest.raises(ImportError, match="rerun-sdk"):
        _ = placeholder.spatial_2d


def test_placeholder_keeps_its_own_identity_attributes() -> None:
    """The metaclass hook must not swallow ordinary class introspection."""
    placeholder = _requires_rerun("RerunViewKind")
    assert placeholder.__name__ == "RerunViewKind"
    assert placeholder.__doc__ is not None
    assert "rerun-sdk" in placeholder.__doc__
