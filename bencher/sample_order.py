from enum import auto
from strenum import StrEnum


class SampleOrder(StrEnum):
    """Controls the sampling traversal order for plot_sweep.

    - INORDER: Traverse inputs in the natural Cartesian product order
                (right-most dimension varies fastest).
    - REVERSED: Traverse the same set of samples in the reverse order.

    Note: This only affects sampling order, not plotting or dataset dimension order.
    """

    INORDER = auto()
    REVERSED = auto()
