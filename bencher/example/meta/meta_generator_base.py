import textwrap
from pathlib import Path

import bencher as bch


class MetaGeneratorBase(bch.ParametrizedSweep):
    """Shared base class for meta-generators that produce Python example files."""

    plots = bch.ResultReference(units="int")

    def generate_example(
        self,
        *,
        title,
        output_dir,
        filename,
        function_name,
        imports,
        body,
    ):
        """Write a runnable Python example file.

        Args:
            title: Docstring / heading text.
            output_dir: Relative path under ``bencher/example/meta/generated/``.
            filename: Python file stem (e.g. ``result_var_1d``).
            function_name: Name of the example function (e.g. ``example_result_var_1d``).
            imports: Import lines placed at the top of the file.
            body: Unindented function body lines (after ``run_cfg`` guard).
                  Indentation is applied automatically.
        """
        indented_body = textwrap.indent(body, "    ")
        content = f'''"""Auto-generated example: {title}."""

{imports}


def {function_name}(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """{title}."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
{indented_body}
    return bench


if __name__ == "__main__":
    bch.run({function_name})
'''
        fpath = Path(f"bencher/example/meta/generated/{output_dir}/{filename}.py")
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return fpath
