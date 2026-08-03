"""Plan 22 D6: declaring a ResultHmap emits a DeprecationWarning (test item 8)."""

import pytest

from bencher.variables.results import ResultHmap


def test_resulthmap_instantiation_warns_deprecation():
    """ResultHmap still works but warns, pointing at the container-based replacement."""
    with pytest.warns(DeprecationWarning, match="ResultContainer") as record:
        rv = ResultHmap()
    assert any("ResultReference" in str(w.message) for w in record)
    assert isinstance(rv, ResultHmap)
