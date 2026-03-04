from pathlib import Path

import nbformat as nbf

import bencher as bch
from bencher.example.meta.generate_examples import _deterministic_id


class MetaGeneratorBase(bch.ParametrizedSweep):
    """Shared base class for meta-generators that produce notebooks programmatically."""

    def generate_notebook(
        self,
        *,
        title,
        output_dir,
        filename,
        setup_code,
        results_code=None,
    ):
        """Create a 3-cell notebook: markdown title, %%capture setup, results display.

        Args:
            title: Markdown heading text.
            output_dir: Relative path under ``docs/reference/meta/`` (e.g. ``result_types/result_bool``).
            filename: Notebook stem (e.g. ``result_bool_1d``).
            setup_code: Full Python code for cell 2. Automatically prefixed with ``%%capture\\n``.
            results_code: Code for cell 3. Defaults to ``output_notebook()`` + ``res.to_auto_plots()``.
        """
        if results_code is None:
            results_code = (
                "from bokeh.io import output_notebook\noutput_notebook()\nres.to_auto_plots()"
            )

        nb = nbf.v4.new_notebook()
        cells = [
            nbf.v4.new_markdown_cell(f"# {title}"),
            nbf.v4.new_code_cell(f"%%capture\n{setup_code}"),
            nbf.v4.new_code_cell(results_code),
        ]

        id_key = f"{output_dir}/{filename}"
        for i, cell in enumerate(cells):
            cell.id = _deterministic_id(id_key, i)
        nb["cells"] = cells

        fname = Path(f"docs/reference/meta/{output_dir}/ex_{filename}.ipynb")
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname.write_text(nbf.writes(nb) + "\n", encoding="utf-8")
