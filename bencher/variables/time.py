from __future__ import annotations

import inspect
import os
import warnings
from datetime import datetime

from pandas import Timestamp
from param import Selector

from bencher.variables.sweep_base import SweepBase, shared_slots

# The package directory, not its parent: every frame under it is bencher's own,
# so the first frame outside it is the caller whose time_src caused the warning.
_BENCHER_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep


def _caller_stacklevel() -> int:
    """Return the stacklevel, from our caller's warn site, of the first non-bencher frame.

    TimeSnapshot is constructed several frames below the public API that accepts
    ``time_src``, and that depth is free to change, so the level is measured rather
    than hardcoded. Level 1 is our caller, so the search starts at 2; an example run
    from under ``bencher/`` has no non-bencher frame at all, so the walk also stops
    at the outermost frame.
    """
    frame = inspect.currentframe()
    level = 0
    while frame is not None and frame.f_back is not None:
        frame = frame.f_back
        level += 1
        filename = os.path.abspath(frame.f_code.co_filename)
        if level >= 2 and not filename.startswith(_BENCHER_PACKAGE_DIR):
            break
    return max(level, 2)


# Split because only the first half is unconditionally true. The object coordinate
# happens to every tz-aware TimeSnapshot; losing history happens only to the one
# that is the over_time axis, because that is the only dataset a stored series is
# reconciled against (see Bench.plot_sweep, which gates load_history_cache on
# run_cfg.over_time).
_TZ_AWARE_COORD_WARNING = (
    "TimeSnapshot was given a timezone-aware datetime. xarray cannot store "
    "tz-aware timestamps as datetime64, so its sweep coordinate becomes dtype "
    "object instead of datetime64[us]."
)

_TZ_AWARE_HISTORY_WARNING = (
    " The history dtype guard compares those dtypes, so switching between naive "
    "and tz-aware timestamps in either direction discards the stored history "
    "(and makes history transfer fail outright); the series restarts from that "
    "run. Whichever kind your existing history was recorded with, keep passing "
    "that kind."
)


class TimeBase(SweepBase, Selector):
    """Base class for time-valued sweep variables.

    Time is represented as a continuous value, i.e. a datetime; see TimeSnapshot for
    what that datetime becomes as a coordinate. To represent time as a discrete value
    use the TimeEvent class. The distinction is because holoviews and plotly code makes
    different assumptions about discrete vs continuous variables.
    """

    def __init__(
        self,
        objects=None,
        default=None,
        instantiate=False,
        compute_default_fn=None,
        check_on_set=None,
        allow_None=None,
        empty_default=False,
        **params,
    ):
        super().__init__(
            objects=objects,
            default=default,
            instantiate=instantiate,
            compute_default_fn=compute_default_fn,
            check_on_set=check_on_set,
            allow_None=allow_None,
            empty_default=empty_default,
            **params,
        )

    __slots__ = shared_slots

    def values(self) -> list[str]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        return self.objects


class TimeSnapshot(TimeBase):
    """A class to capture a time snapshot of benchmark values as a continuous value.

    A naive datetime becomes a datetime64[us] coordinate. A timezone-aware one is kept
    as a tz-aware Timestamp, because xarray has no tz-aware datetime64, so the
    coordinate is dtype object instead; as the over_time axis, that dtype difference is
    what the history guard rejects. To represent time as a discrete value use the
    TimeEvent class. The distinction is because holoviews and plotly code makes
    different assumptions about discrete vs continuous variables.
    """

    __slots__ = shared_slots

    def __init__(
        self,
        datetime_src: datetime | str,
        units: str = "time",
        samples: int | None = None,
        *,
        history_axis: bool = False,
        **params,
    ):
        """Build a single-timestamp sweep variable.

        Args:
            datetime_src: The timestamp, or a string event name.
            units: Axis units label.
            samples: Sample count; defaults to the number of objects.
            history_axis: True when this snapshot is the ``over_time`` axis a
                stored history series is reconciled against, which is the only
                case where a tz-aware timestamp can cost you that history.
        """
        if isinstance(datetime_src, str):
            TimeBase.__init__(self, [datetime_src], instantiate=True, **params)
        else:
            if isinstance(datetime_src, datetime) and datetime_src.tzinfo is not None:
                message = _TZ_AWARE_COORD_WARNING
                if history_axis:
                    message += _TZ_AWARE_HISTORY_WARNING
                warnings.warn(message, UserWarning, stacklevel=_caller_stacklevel())
            TimeBase.__init__(
                self,
                objects=[Timestamp(datetime_src)],
                instantiate=True,
                **params,
            )
        self.units = units
        self.optimize = False
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples


class TimeEvent(TimeBase):
    """A class to represent a discrete event in time where the data was captured i.e a series of pull requests.  Here time is discrete and can't be interpolated, to represent time as a continuous value use the TimeSnapshot class.  The distinction is because holoview and plotly code makes different assumptions about discrete vs continuous variables"""

    __slots__ = shared_slots

    def __init__(
        self,
        time_event: str,
        units: str = "event",
        samples: int | None = None,
        **params,
    ):
        TimeBase.__init__(
            self,
            objects=[time_event],
            instantiate=True,
            **params,
        )
        self.units = units
        self.optimize = False
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples
