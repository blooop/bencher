import pytest
import panel as pn

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

    def test_backward_compat_horizontal_true(self):
        """horizontal=True was Column (down) in the old code."""
        c = ComposableContainerPanel(horizontal=True)
        c.append(pn.pane.Markdown("A"))
        result = c.render()
        assert isinstance(result, pn.Column)

    def test_backward_compat_horizontal_false(self):
        """horizontal=False was Row (right) in the old code."""
        c = ComposableContainerPanel(horizontal=False)
        c.append(pn.pane.Markdown("A"))
        result = c.render()
        assert isinstance(result, pn.Row)

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
            nesting_depth=2,
            background_col="#ff0000",
        )
        styles = c.container.styles
        assert "border-bottom" in styles
        assert styles["background"] == "#ff0000"

    def test_border_is_thin_regardless_of_depth(self):
        """Nesting depth must NOT thicken the divider — depth is shown via background tint."""
        shallow = ComposableContainerPanel(compose_method=ComposeType.right, nesting_depth=1)
        deep = ComposableContainerPanel(compose_method=ComposeType.right, nesting_depth=5)
        assert shallow.container.styles["border-bottom"] == deep.container.styles["border-bottom"]

    def test_label_nowrap_styles(self):
        """Labels must carry the CSS that prevents Markdown wrapping — replaces the old max_len*7 hack."""
        c = ComposableContainerPanel(compose_method=ComposeType.right, var_name="x", var_value="1")
        c.append(pn.pane.Markdown("A"))
        label_pane = c.render()[0]
        assert label_pane.styles.get("white-space") == "nowrap"
        assert label_pane.styles.get("min-width") == "max-content"
