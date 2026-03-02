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


def execute_all_notebooks(
    notebooks: list[Path], timeout: int = 600, max_workers: int | None = None
) -> None:
    """Execute notebooks in parallel using a process pool."""
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, len(notebooks))

    print(f"Executing {len(notebooks)} notebooks with {max_workers} workers...")
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(execute_notebook, nb, timeout): nb for nb in notebooks}
        for future in as_completed(futures):
            nb_path = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"FAILED {nb_path}: {exc}")
                raise


if __name__ == "__main__":
    # Meta examples only (generated programmatically via BenchMetaGen sweeps)
    meta_dir = Path("docs/reference/meta")
    if meta_dir.exists():
        shutil.rmtree(meta_dir)
    meta_dir.mkdir(parents=True, exist_ok=True)

    from bencher.example.meta.generate_meta import example_meta

    example_meta()

    # Collect all notebooks to execute
    all_notebooks = sorted(meta_dir.rglob("*.ipynb"))

    # Also include non-meta gallery notebooks (levels, pareto, yaml, etc.)
    gallery_notebooks = sorted(Path("docs/reference").glob("*/*.ipynb"))
    gallery_notebooks = [nb for nb in gallery_notebooks if "meta" not in nb.parts]
    all_notebooks.extend(gallery_notebooks)

    # Execute all notebooks in parallel so RTD only renders pre-computed results
    execute_all_notebooks(all_notebooks)
