"""Claims a change is meant to make true, declared on a result variable.

``bn.ResultFloat(units="m", claim="< 0.7")`` says every sample of this metric must
be below 0.7. The string is parsed once, when the result variable is constructed,
into a :data:`Claim`: an unreadable claim fails where the class is defined, not
after a sweep has run.

A claim is judged against *every* sample a sweep took, repeats included, so it
holds only if the worst sample satisfies it -- the largest value for ``<``/``<=``,
the smallest for ``>``/``>=``, and the one nearest (or furthest past) an edge for a
range. A mean inside the bound with one point outside it is a failed claim.

Grammar::

    < 0.7      <= 0.7      > 0.5      >= 0.5      0.5..0.7   (inclusive range)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, assert_never

import numpy as np
from strenum import StrEnum

if TYPE_CHECKING:
    import xarray as xr


class Comparison(StrEnum):
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


@dataclass(frozen=True)
class Threshold:
    """Every sample compares to ``bound`` as ``op`` says."""

    op: Comparison
    bound: float

    def __str__(self) -> str:
        return f"{self.op.value} {self.bound:g}"


@dataclass(frozen=True)
class Within:
    """Every sample lies in ``[low, high]``."""

    low: float
    high: float

    def __post_init__(self) -> None:
        if not self.low <= self.high:
            raise ValueError(f"claim range {self.low:g}..{self.high:g} is empty")

    def __str__(self) -> str:
        return f"{self.low:g}..{self.high:g}"


Claim = Threshold | Within

_THRESHOLD = re.compile(r"^\s*(<=|>=|<|>)\s*(\S+)\s*$")
_RANGE = re.compile(r"^\s*(\S+?)\s*\.\.\s*(\S+)\s*$")


def _finite(token: str, text: str) -> float:
    try:
        value = float(token)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ValueError(f"claim {text!r}: {token!r} is not a finite number")
    return value


def parse_claim(text: str) -> Claim:
    """Parse a claim string; raise ``ValueError`` naming the claim if it is unreadable."""
    if match := _THRESHOLD.match(text):
        return Threshold(Comparison(match[1]), _finite(match[2], text))
    if match := _RANGE.match(text):
        try:
            return Within(_finite(match[1], text), _finite(match[2], text))
        except ValueError as exc:
            raise ValueError(f"claim {text!r}: {exc}") from exc
    raise ValueError(f"claim {text!r} is not one of '< x', '<= x', '> x', '>= x' or 'low..high'")


def as_claim(value: str | Claim | None) -> Claim | None:
    """Accept a claim string or an already-parsed claim (a pickled result var carries one)."""
    if value is None or isinstance(value, (Threshold, Within)):
        return value
    if isinstance(value, str):
        return parse_claim(value)
    raise TypeError(f"claim must be a string such as '< 0.7', not {value!r}")


def _margin(claim: Claim, values: np.ndarray) -> np.ndarray:
    """How far inside the claim each value is; the worst sample has the smallest margin."""
    match claim:
        case Threshold(op=op, bound=bound):
            match op:
                case Comparison.LT | Comparison.LE:
                    return bound - values
                case Comparison.GT | Comparison.GE:
                    return values - bound
                case _ as unreachable:
                    assert_never(unreachable)
        case Within(low=low, high=high):
            return np.minimum(values - low, high - values)
        case _ as unreachable:
            assert_never(unreachable)


def _admits(claim: Claim, value: float) -> bool:
    match claim:
        case Threshold(op=op, bound=bound):
            match op:
                case Comparison.LT:
                    return value < bound
                case Comparison.LE:
                    return value <= bound
                case Comparison.GT:
                    return value > bound
                case Comparison.GE:
                    return value >= bound
                case _ as unreachable:
                    assert_never(unreachable)
        case Within(low=low, high=high):
            return low <= value <= high
        case _ as unreachable:
            assert_never(unreachable)


@dataclass(frozen=True)
class WorstSample:
    value: float
    inputs: dict


@dataclass(frozen=True)
class Holds:
    worst: WorstSample
    samples: int


@dataclass(frozen=True)
class Fails:
    worst: WorstSample
    samples: int


@dataclass(frozen=True)
class Unmeasured:
    """The metric has no recorded sample, so the claim can be neither held nor failed."""


ClaimOutcome = Holds | Fails | Unmeasured


def _scalar(value: Any) -> Any:
    """Unwrap a numpy scalar coordinate to its Python value so it serialises to JSON."""
    return value.item() if hasattr(value, "item") else value


def evaluate_claim(claim: Claim, da: xr.DataArray) -> ClaimOutcome:
    """Judge *claim* against every recorded sample in *da*.

    NaN is bencher's "not recorded" marker, so it is skipped rather than judged.
    The worst sample's coordinates (sweep inputs and ``repeat``) are reported so
    a failure names where to look.
    """
    values = np.asarray(da.values, dtype=float)
    recorded = ~np.isnan(values)
    if not recorded.any():
        return Unmeasured()
    margins = np.where(recorded, _margin(claim, values), np.inf)
    flat = int(np.argmin(margins))
    index = np.unravel_index(flat, values.shape)
    inputs = {
        dim: _scalar(da[dim].values[i]) if dim in da.coords else int(i)
        for dim, i in zip(da.dims, index, strict=True)
    }
    worst = WorstSample(float(values[index]), inputs)
    samples = int(recorded.sum())
    return Holds(worst, samples) if _admits(claim, worst.value) else Fails(worst, samples)


def outcome_to_dict(outcome: ClaimOutcome) -> dict:
    """Flatten an outcome for JSON: ``holds`` is ``None`` when nothing was measured."""
    match outcome:
        case Holds(worst=worst, samples=samples) | Fails(worst=worst, samples=samples):
            return {
                "holds": isinstance(outcome, Holds),
                "worst_value": worst.value if math.isfinite(worst.value) else None,
                "worst_inputs": worst.inputs,
                "samples": samples,
            }
        case Unmeasured():
            return {"holds": None, "worst_value": None, "worst_inputs": {}, "samples": 0}
        case _ as unreachable:
            assert_never(unreachable)
