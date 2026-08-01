import panel as pn
import pytest

from bencher.results.composable_container.composable_container_base import ComposeType
from bencher.results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
)


def _make_container(compose_method, **kwargs):
    c = ComposableContainerPanel(compose_method=compose_method, **kwargs)
    c.append(pn.pane.Markdown("A"))
    c.append(pn.pane.Markdown("B"))
    return c


class TestComposableContainerPanel:
    def test_right_creates_row(self):
        c = _make_container(ComposeType.right)
        result = c.render()
        assert isinstance(result, pn.Row)

    def test_down_creates_column(self):
        c = _make_container(ComposeType.down)
        result = c.render()
        assert isinstance(result, pn.Column)

    def test_sequence_creates_tabs(self):
        c = _make_container(ComposeType.sequence)
        result = c.render()
        # render() returns a Column wrapper containing the Tabs
        assert isinstance(result, pn.Column)
        # The last child should be the Tabs
        tabs = result[-1]
        assert isinstance(tabs, pn.Tabs)
        assert len(tabs) == 2

    def test_overlay_returns_layout(self):
        c = _make_container(ComposeType.overlay)
        result = c.render()
        assert isinstance(result, pn.layout.ListLike)

    def test_label_with_var_name_value(self):
        c = ComposableContainerPanel(compose_method=ComposeType.right, var_name="x", var_value="1")
        c.append(pn.pane.Markdown("A"))
        result = c.render()
        # The label should be prepended as the first child
        assert len(result) >= 2
        assert isinstance(result[0], pn.pane.Markdown)
        label_pane = result[0]
        assert "x" in str(label_pane.object)
        assert "1" in str(label_pane.object)

    def test_label_with_sequence_sits_outside_tabs(self):
        """For sequence mode, the label sits outside the tab bar in the wrapper Column."""
        c = ComposableContainerPanel(
            compose_method=ComposeType.sequence, var_name="step", var_value="1"
        )
        c.append(pn.pane.Markdown("A"))
        result = c.render()
        assert isinstance(result, pn.Column)
        # First child is the label, second is the Tabs
        assert isinstance(result[0], pn.pane.Markdown)
        assert "step" in str(result[0].object)
        assert isinstance(result[1], pn.Tabs)

    @pytest.mark.parametrize("compose_method", list(ComposeType))
    def test_compose_method_is_never_overwritten(self, compose_method):
        """Plan 23 P8: `horizontal` silently overwrote compose_method, inverted at that.

        `horizontal=True` mapped to `down` here while `_to_panes_da` maps the same flag
        to `right`, so the two spellings of one concept disagreed.  Only compose_method
        remains.
        """
        assert ComposableContainerPanel(compose_method=compose_method).compose_method is (
            compose_method
        )

    def test_horizontal_kwarg_is_gone(self):
        # The removed kwarg is the point of the test, so both checkers must tolerate it
        # here -- and both flagging it is itself evidence that it is gone.
        # pylint: disable=unexpected-keyword-arg
        with pytest.raises(TypeError):
            ComposableContainerPanel(horizontal=True)  # ty: ignore[unknown-argument]

    @pytest.mark.parametrize("compose_method", list(ComposeType))
    def test_tabs_declared_for_every_compose_method(self, compose_method):
        """_tabs exists on every instance; only the sequence arm fills it in."""
        c = ComposableContainerPanel(compose_method=compose_method)
        tabs = c._tabs  # pylint: disable=protected-access
        assert (tabs is not None) == (compose_method == ComposeType.sequence)

    def test_unknown_compose_method_fails_at_construction(self):
        """Before P8 the match had no final arm: `align` stayed unbound and the
        failure surfaced as an UnboundLocalError three frames from the cause."""
        with pytest.raises(AssertionError):
            ComposableContainerPanel(compose_method="not_a_compose_type")

    @pytest.mark.parametrize("compose_type", list(ComposeType))
    def test_render_returns_panel_for_all_types(self, compose_type):
        c = _make_container(compose_type)
        result = c.render()
        assert isinstance(result, pn.layout.ListLike)

    def test_container_is_panel_layout(self):
        """container attribute should be a Panel layout for backward compat with _to_panes_da."""
        c = _make_container(ComposeType.right)
        assert isinstance(c.container, pn.layout.ListLike)

    def test_styles_border_and_background(self):
        c = ComposableContainerPanel(
            compose_method=ComposeType.right,
            width=2,
            background_col="#ff0000",
        )
        styles = c.container.styles
        assert "border-bottom" in styles
        assert styles["background"] == "#ff0000"
