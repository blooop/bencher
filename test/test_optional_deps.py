"""How bencher.optional_deps turns a missing heavy package into an install hint."""

from __future__ import annotations

import pickle

import pytest

from bencher.optional_deps import (
    FullInstallRequiredError,
    _MissingModule,
    full_install_required,
)


def _missing(name: str) -> ModuleNotFoundError:
    return ModuleNotFoundError(f"No module named {name!r}", name=name)


def test_a_missing_heavy_package_says_to_install_holobench():
    with (
        pytest.raises(FullInstallRequiredError, match="pip install holobench") as info,
        full_install_required(),
    ):
        raise _missing("holoviews.plotting")
    assert isinstance(info.value, ImportError)
    assert info.value.name == "holoviews.plotting"


def test_a_missing_light_package_is_left_alone():
    """A package holobench-core should have is a broken install, not a missing extra."""
    with pytest.raises(ModuleNotFoundError) as info, full_install_required():
        raise _missing("xarray")
    assert not isinstance(info.value, FullInstallRequiredError)


def test_the_stand_in_raises_the_hint_on_use():
    pn = _MissingModule("panel", _missing("panel"))
    with pytest.raises(FullInstallRequiredError, match=r"'panel'.*pip install holobench"):
        pn.Column  # noqa: B018 - the attribute read is what raises


def test_the_stand_in_answers_dunder_probes_like_a_module():
    """hasattr, getattr with a default and pickle probe dunders; they must not raise the hint."""
    pn = _MissingModule("panel", _missing("panel"))
    assert not hasattr(pn, "__wrapped__")
    assert getattr(pn, "__version__", None) is None
    with pytest.raises(TypeError):  # a module never pickles; the point is it is not the hint
        pickle.dumps(pn)
