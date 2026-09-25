from enum import auto

from strenum import StrEnum


class SampleOrder(StrEnum):
    """Controls the sampling traversal order for plot_sweep.

    - INORDER: Traverse inputs in the natural Cartesian product order
                (right-most dimension varies fastest).
    - REVERSED: Traverse the same set of samples in the reverse order.
    - ROUND_ROBIN: Sample every input point once per round, one round per repeat,
                   so repeat r of every point is taken before repeat r+1 of any.
                   Spreads each point's repeats across the whole run, so a drift
                   over time (thermals, load) is not confounded with an input.

    Note: This only affects sampling order, not plotting or dataset dimension order.
    """

    INORDER = auto()
    REVERSED = auto()
    ROUND_ROBIN = auto()
