"""bencher.grammar — the typed core of A6's grammar of N-D data.

Re-exports only; no logic (plan 25 D1). Import direction is one-way: rendering code may
import this package; nothing here imports `bencher.results`, `bencher.plugins`, or any
rendering library — enforced by `test/test_grammar.py`.
"""

from bencher.grammar.capability import (
    RERUN_CAPABILITIES,
    SUBSTITUTION_CHAIN,
    Approx,
    BackendCapabilities,
    Capability,
    Direct,
    EvalMode,
    Lowering,
    Native,
    NoLowering,
    Substituted,
    Unsupported,
    substitute,
)
from bencher.grammar.channels import GRAMMAR_VERSION, Channel
from bencher.grammar.compose import Compose, compose

__all__ = [
    "GRAMMAR_VERSION",
    "RERUN_CAPABILITIES",
    "SUBSTITUTION_CHAIN",
    "Approx",
    "BackendCapabilities",
    "Capability",
    "Channel",
    "Compose",
    "Direct",
    "EvalMode",
    "Lowering",
    "Native",
    "NoLowering",
    "Substituted",
    "Unsupported",
    "compose",
    "substitute",
]
