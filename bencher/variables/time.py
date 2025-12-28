from datetime import datetime
from typing import List

from pandas import Timestamp
from param import Selector
from bencher.variables.sweep_base import SweepBase, shared_slots


class TimeBase(SweepBase, Selector):
    """A class to capture a time snapshot of benchmark values.  Time is represent as a continuous value i.e a datetime which is converted into a np.datetime64.  To represent time as a discrete value use the TimeEvent class. The distinction is because holoview and plotly code makes different assumptions about discrete vs continuous variables"""

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

    def values(self) -> List[str]:
        """return all the values for a parameter sweep.  If debug is true return a reduced list"""
        # print(self.sampling_str(debug))
        return self.objects


class TimeSnapshot(TimeBase):
    """A class to capture a time snapshot of benchmark values.  Time is represent as a continuous value i.e a datetime which is converted into a np.datetime64.  To represent time as a discrete value use the TimeEvent class. The distinction is because holoview and plotly code makes different assumptions about discrete vs continuous variables"""

    __slots__ = shared_slots

    def __init__(
        self,
        datetime_src: datetime | str,
        units: str = "time",
        samples: int | None = None,
        **params,
    ):
        if isinstance(datetime_src, str):
            TimeBase.__init__(self, [datetime_src], instantiate=True, **params)
        else:
            TimeBase.__init__(
                self,
                objects=[Timestamp(datetime_src)],
                instantiate=True,
                **params,
            )
        self.units = units
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
        if samples is None:
            self.samples = len(self.objects)
        else:
            self.samples = samples
