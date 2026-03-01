import hashlib
import subprocess

import nbformat as nbf
from pathlib import Path


def _deterministic_id(name: str, index: int) -> str:
    """Generate a deterministic 8-char hex cell ID from a name and cell index."""
    return hashlib.sha256(f"{name}:{index}".encode()).hexdigest()[:8]


def convert_example_to_jupyter_notebook(
    filename: str, output_path: str, repeats: int | None = None
) -> None:
    source_path = Path(filename)

    nb = nbf.v4.new_notebook()
    title = source_path.stem
    repeat_exr = f"bch.BenchRunCfg(repeats={repeats})" if repeats else ""
    function_name = f"{source_path.stem}({repeat_exr})"
    text = f"""# {title}"""

    code = "%%capture\n"

    example_code = source_path.read_text(encoding="utf-8")
    split_code = example_code.split("""if __name__ == "__main__":""")
    code += split_code[0]

    code += f"bench = {function_name}"

    code_results = """from bokeh.io import output_notebook

output_notebook()
bench.get_result().to_auto_plots()"""

    cells = [
        nbf.v4.new_markdown_cell(text),
        nbf.v4.new_code_cell(code),
        nbf.v4.new_code_cell(code_results),
    ]
    for i, cell in enumerate(cells):
        cell.id = _deterministic_id(title, i)
    nb["cells"] = cells
    output_path = Path(f"docs/reference/{output_path}/ex_{title}.ipynb")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Add a newline character at the end to ensure proper end-of-file
    notebook_content = nbf.writes(nb) + "\n"
    output_path.write_text(notebook_content, encoding="utf-8")
    subprocess.run(["ruff", "format", str(output_path)], check=False)


if __name__ == "__main__":
    # Meta examples only (generated programmatically via BenchMetaGen sweeps)
    from bencher.example.meta.generate_meta import example_meta

    example_meta()
