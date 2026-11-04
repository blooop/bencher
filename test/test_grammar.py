"""Tests for bencher.grammar — the Laws 3/4/5 foundation (issue #1108's rulings).

Three contracts are pinned here: the closed channel vocabulary (Law 5), the `Compose`
node (Law 4), and the capability-table/substitution embryo (Law 3) — plus the
direction-of-import rule that replaces plan 25 D1's isolation grep.
"""

import ast
import dataclasses
from pathlib import Path
from typing import ClassVar

import pytest

from bencher.grammar import (
    GRAMMAR_VERSION,
    RERUN_CAPABILITIES,
    Approx,
    BackendCapabilities,
    Channel,
    Compose,
    Direct,
    EvalMode,
    Native,
    NoLowering,
    Substituted,
    Unsupported,
    compose,
    substitute,
)
from bencher.grammar import capability as capability_module

GRAMMAR_DIR = Path(__file__).parent.parent / "bencher" / "grammar"


class TestChannelVocabulary:
    def test_member_set_is_pinned(self):
        """Law 5: exactly nine members with these exact values. Adding, removing, or
        renaming one must land here as a visible, reviewed diff plus a GRAMMAR_VERSION
        bump — the values are Law 8's future kwarg names, so each is a contract."""
        assert {m.name: m.value for m in Channel} == {
            "X": "x",
            "Y": "y",
            "Z": "z",
            "OVERLAY": "overlay",
            "FACET_ROW": "facet_row",
            "FACET_COL": "facet_col",
            "TABS": "tabs",
            "TIME": "time",
            "SPREAD": "spread",
        }

    def test_rejected_candidates_are_absent(self):
        """Color/Style/Dash/Animation/EntityPath are settled owner rejections (Law 5)."""
        values = {m.value for m in Channel}
        assert values.isdisjoint({"color", "style", "dash", "animation", "entity_path"})

    def test_grammar_version(self):
        assert GRAMMAR_VERSION == "1"


class TestCompose:
    def test_zero_items_is_unrepresentable(self):
        with pytest.raises(ValueError, match="zero items"):
            Compose(items=(), along=Channel.TABS)

    def test_factory_accepts_channel_value_strings(self):
        node = compose(["a", "b"], along="facet_col")
        assert node == Compose(items=("a", "b"), along=Channel.FACET_COL)

    def test_factory_rejects_non_channel_strings(self):
        with pytest.raises(ValueError):
            compose(["a"], along="sequence")  # ComposeType's vocabulary, not the grammar's

    def test_nodes_nest(self):
        inner = compose(["a", "b"], along=Channel.OVERLAY)
        outer = compose([inner, "c"], along=Channel.FACET_ROW)
        assert outer.items[0] is inner

    def test_node_is_frozen(self):
        node = compose(["a"], along=Channel.TABS)
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.along = Channel.X


class TestCapabilityTable:
    def test_partial_table_is_unrepresentable(self):
        """Totality by construction: forgetting to classify a channel is a constructor
        error naming the gap, not a KeyError at plan time."""
        with pytest.raises(ValueError, match="SPREAD"):
            BackendCapabilities(
                backend="partial",
                channels={
                    c: Native(mode=EvalMode.VIEW) for c in Channel if c is not Channel.SPREAD
                },
            )

    def test_rerun_seed_is_total(self):
        assert set(RERUN_CAPABILITIES.channels) == set(Channel)


def _all_unsupported_except(supported: dict[Channel, Native | Approx]) -> BackendCapabilities:
    channels: dict[Channel, Native | Approx | Unsupported] = {
        c: Unsupported(why=f"{c} not lowerable") for c in Channel
    }
    channels.update(supported)
    return BackendCapabilities(backend="synthetic", channels=channels)


class TestSubstitute:
    def test_supported_channel_lowers_directly(self):
        outcome = substitute(RERUN_CAPABILITIES, Channel.TIME)
        assert outcome == Direct(channel=Channel.TIME, capability=Native(mode=EvalMode.VIEW))

    def test_declared_gap_walks_the_chain(self):
        """A6 §3's declared rerun gap: Spread → Overlay, with the walk recorded."""
        outcome = substitute(RERUN_CAPABILITIES, Channel.SPREAD)
        assert isinstance(outcome, Substituted)
        assert outcome.channel is Channel.OVERLAY
        assert outcome.via == (Channel.SPREAD, Channel.OVERLAY)

    def test_exhausted_chain_reports_every_refusal(self):
        """Spread → Overlay → FacetCol all unsupported and FacetCol has no successor:
        the outcome names each refusal instead of raising or silently dropping."""
        table = _all_unsupported_except({Channel.X: Native(mode=EvalMode.VIEW)})
        outcome = substitute(table, Channel.SPREAD)
        assert isinstance(outcome, NoLowering)
        assert outcome.requested is Channel.SPREAD
        for c in (Channel.SPREAD, Channel.OVERLAY, Channel.FACET_COL):
            assert str(c) in outcome.reason

    def test_chain_cycle_terminates(self, monkeypatch):
        monkeypatch.setitem(capability_module.SUBSTITUTION_CHAIN, Channel.FACET_COL, Channel.SPREAD)
        table = _all_unsupported_except({})
        outcome = substitute(table, Channel.SPREAD)
        assert isinstance(outcome, NoLowering)


class TestImportDirection:
    """#1108 ruling 4: renderers may import grammar; grammar imports no rendering
    module — the direction-of-import rule that replaces plan 25 D1's isolation grep."""

    # Module prefixes the grammar package must never import: bencher's rendering/report
    # layers and every rendering library. Extending grammar never loosens this list.
    FORBIDDEN_PREFIXES = (
        "bencher.results",
        "bencher.plugins",
        "bencher.bench_report",
        "bencher.render",
        "panel",
        "holoviews",
        "hvplot",
        "plotly",
        "bokeh",
        "matplotlib",
        "rerun",
        "xarray",
        "param",
    )

    # Plan 25 D1's one-way intra-package order: channels.py imports nothing from the
    # package; every other module may import only what is listed here.
    INTRA_PACKAGE_ALLOWED: ClassVar[dict[str, set[str]]] = {
        "__init__": {
            "bencher.grammar.channels",
            "bencher.grammar.compose",
            "bencher.grammar.capability",
        },
        "channels": set(),
        "compose": {"bencher.grammar.channels"},
        "capability": {"bencher.grammar.channels"},
    }

    @staticmethod
    def _imported_modules(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
        return found

    def test_grammar_imports_no_rendering_module(self):
        for path in sorted(GRAMMAR_DIR.glob("*.py")):
            for module in self._imported_modules(path):
                assert not module.startswith(self.FORBIDDEN_PREFIXES), (
                    f"{path.name} imports {module}; grammar must stay import-free of "
                    "rendering modules (#1108 ruling 4)"
                )

    def test_intra_package_imports_are_one_way(self):
        for path in sorted(GRAMMAR_DIR.glob("*.py")):
            allowed = self.INTRA_PACKAGE_ALLOWED[path.stem]
            internal = {m for m in self._imported_modules(path) if m.startswith("bencher.grammar")}
            assert internal <= allowed, (
                f"{path.name} imports {sorted(internal - allowed)}; plan 25 D1's "
                "dependency order is strictly one-way"
            )

    def test_every_grammar_module_is_covered(self):
        assert {p.stem for p in GRAMMAR_DIR.glob("*.py")} == set(self.INTRA_PACKAGE_ALLOWED)
