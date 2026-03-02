import hashlib
import shutil
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


def execute_notebook(notebook_path: str | Path, timeout: int = 600) -> None:
    """Execute a notebook in-place, embedding outputs."""
    import nbclient

    notebook_path = Path(notebook_path)
    print(f"Executing {notebook_path}...")
    nb = nbf.read(notebook_path, as_version=4)
    client = nbclient.NotebookClient(nb, timeout=timeout, kernel_name="python3")
    client.execute()
    nbf.write(nb, notebook_path)


def execute_all_notebooks(directory: str | Path, timeout: int = 600) -> None:
    """Execute all .ipynb files under a directory tree in-place."""
    directory = Path(directory)
    notebooks = sorted(directory.rglob("*.ipynb"))
    print(f"Found {len(notebooks)} notebooks to execute in {directory}")
    for notebook in notebooks:
        execute_notebook(notebook, timeout=timeout)


if __name__ == "__main__":
    # Meta examples only (generated programmatically via BenchMetaGen sweeps)
    meta_dir = Path("docs/reference/meta")
    if meta_dir.exists():
        shutil.rmtree(meta_dir)
    meta_dir.mkdir(parents=True, exist_ok=True)

    from bencher.example.meta.generate_meta import example_meta

    example_meta()

    # Execute all generated meta notebooks in-place so they contain outputs.
    # This allows RTD to render them without re-running the benchmarks.
    execute_all_notebooks(meta_dir)

    # Also execute non-meta gallery notebooks (levels, pareto, yaml)
    gallery_notebooks = sorted(Path("docs/reference").glob("*/*.ipynb"))
    # Filter out meta notebooks (already executed above)
    gallery_notebooks = [nb for nb in gallery_notebooks if "meta" not in nb.parts]
    print(f"Found {len(gallery_notebooks)} non-meta gallery notebooks to execute")
    for nb_path in gallery_notebooks:
        execute_notebook(nb_path)
