import panel as pn
from panel.pane import LaTeX
from typing import Optional, List, Any

pn.extension("mathjax")


def latex_text(text: str) -> str:
    """Convert text to LaTeX text format, replacing underscores with spaces."""
    return r"\text{" + text.replace("_", " ") + r"} \\"


def format_values_list(values: List[Any], max_display: int = 5) -> List[Any]:
    """Format a list of values, showing ellipsis if too long."""
    if len(values) <= max_display:
        return values
    return [values[i] for i in [0, 1, 0, -2, -1]]


def create_matrix_array(values: List[Any]) -> str:
    """Create a LaTeX matrix array from values."""
    displayed_vals = format_values_list(values)
    if len(values) > 5:
        displayed_vals[2] = "⋮"
    return r"\\ ".join([str(val) for val in displayed_vals])


def input_var_to_latex(input_var) -> str:
    """Convert input variable to LaTeX format."""
    vals = input_var.values()
    latex_str = r"\begin{array}{c}"
    latex_str += latex_text(input_var.name)
    latex_str += f"{len(vals)}" + r"\times1 \\"
    latex_str += r"\left[ \begin{array}{c}"
    latex_str += create_matrix_array(vals)
    latex_str += r"\end{array} \right] \end{array}"
    return latex_str


def result_var_to_latex(bench_cfg) -> str:
    """Convert result variables to LaTeX format."""
    sizes = [str(len(i.values())) for i in bench_cfg.all_vars]
    if len(sizes) == 1:
        sizes.insert(0, "1")

    latex_str = r"\begin{array}{c}"
    latex_str += r"\times".join(reversed(sizes)) + r"\\ of \\"
    latex_str += r" \left[\begin{array}{cc}"
    latex_str += "".join(latex_text(rv.name) for rv in bench_cfg.result_vars)
    latex_str += r"\end{array} \right]\end{array}"
    return latex_str


def to_latex(bench_cfg) -> Optional[pn.pane.LaTeX]:
    """Convert benchmark configuration to LaTeX visualization.

    Returns None if there are no variables to display.
    """
    if not bench_cfg.all_vars:
        return None

    latex_str = r"\[" + r"\bigtimes".join(input_var_to_latex(iv) for iv in bench_cfg.all_vars)
    latex_str += r"\rightarrow\quad"
    latex_str += result_var_to_latex(bench_cfg)
    latex_str += r"\]"

    return LaTeX(latex_str.replace("_", r"\;"))
