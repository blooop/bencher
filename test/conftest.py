from __future__ import annotations

# Configure Hypothesis once for the whole test suite.
# Disabling the example database avoids opening a global sqlite3 connection,
# which triggers ResourceWarning on Python 3.13 if left to GC.
from hypothesis import settings


settings.register_profile("no_db", database=None)
settings.load_profile("no_db")

