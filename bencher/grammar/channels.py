"""The closed dimension-assignment vocabulary — A6 Law 5.

`Channel` is the complete set of ways a dataset dimension can be assigned to report
structure. It is deliberately closed: anything that is not a dimension assignment is
mark styling, and marks are the open, plugin-registered side of the grammar.

Rejected candidates, settled by owner ruling (A6 Law 5): `Color` (the plotting-backend
styling parameter of `Overlay`, not a channel), `Style`/`Dash` (a second overlay dim),
`Animation` (distinct from `Time`), `EntityPath` (a rerun lowering detail).
"""

from strenum import StrEnum

# Versions the vocabulary itself: plans embed it, and any change to the member set
# bumps it (A6 Law 5). Assignment *policy* is versioned separately (POLICY_VERSION,
# arriving with the phase-3 planner).
GRAMMAR_VERSION = "1"


class Channel(StrEnum):
    """Closed dimension-assignment vocabulary — A6 Law 5. Adding a member requires a
    GRAMMAR_VERSION bump and an owner-reviewed grammar change.

    Values are explicit lowercase strings, never ``auto()``: they become Law 8's kwarg
    names in phase 5 and golden-file content before that, so each value is a contract.
    """

    X = "x"
    Y = "y"
    Z = "z"
    OVERLAY = "overlay"
    FACET_ROW = "facet_row"
    FACET_COL = "facet_col"
    TABS = "tabs"
    TIME = "time"
    SPREAD = "spread"
