"""Constructing a sweep variable must not raise a param deprecation warning."""

import enum
import warnings
from datetime import datetime

import pytest

import bencher as bn
from bencher.variables.time import TimeEvent, TimeSnapshot


class _Colour(enum.Enum):
    RED = "red"
    BLUE = "blue"


CONSTRUCTORS = {
    "TimeSnapshot(datetime)": lambda: TimeSnapshot(datetime(2024, 1, 1)),
    "TimeSnapshot(str)": lambda: TimeSnapshot("run_1"),
    "TimeEvent": lambda: TimeEvent("pr_1"),
    "StringSweep": lambda: bn.StringSweep(["a", "b"]),
    "BoolSweep": lambda: bn.BoolSweep(),
    "EnumSweep": lambda: bn.EnumSweep(_Colour),
    "IntSweep": lambda: bn.IntSweep(default=1, bounds=[0, 5]),
    "FloatSweep": lambda: bn.FloatSweep(default=1.0, bounds=[0.0, 5.0]),
    "ResultFloat": lambda: bn.ResultFloat(units="s"),
    "ResultString": lambda: bn.ResultString(),
    "ResultPath": lambda: bn.ResultPath(),
}


@pytest.mark.parametrize("make", CONSTRUCTORS.values(), ids=CONSTRUCTORS.keys())
def test_construction_raises_no_deprecation_warning(make):
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        make()
