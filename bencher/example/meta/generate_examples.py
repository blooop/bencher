import nbformat as nbf
from pathlib import Path
import hashlib


def get_deterministic_cell_id(content: str, cell_type: str) -> str:
    """Generate a deterministic cell ID based on content and type."""
    # Create a hash from the cell content and type
    hash_input = f"{cell_type}:{content}"
    return hashlib.md5(hash_input.encode()).hexdigest()


def convert_example_to_jupyter_notebook(
    filename: str, output_path: str, repeats: int = None
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

    code += f"""
bench={function_name}
"""

    code_results = """
from bokeh.io import output_notebook
output_notebook()
bench.get_result().to_auto_plots()
"""

    # Create cells with deterministic IDs
    markdown_cell = nbf.v4.new_markdown_cell(text)
    markdown_cell["id"] = get_deterministic_cell_id(text, "markdown")

    code_cell = nbf.v4.new_code_cell(code)
    code_cell["id"] = get_deterministic_cell_id(code, "code")

    results_cell = nbf.v4.new_code_cell(code_results)
    results_cell["id"] = get_deterministic_cell_id(code_results, "code")

    nb["cells"] = [markdown_cell, code_cell, results_cell]
    output_path = Path(f"docs/reference/{output_path}/ex_{title}.ipynb")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Add a newline character at the end to ensure proper end-of-file
    notebook_content = nbf.writes(nb) + "\n"
    output_path.write_text(notebook_content, encoding="utf-8")


if __name__ == "__main__":
    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0D/example_0_in_1_out.py", "0D", repeats=100
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0D/example_0_in_2_out.py", "0D", repeats=100
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1D/example_1_int_in_1_out.py", "1D"
    )
    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1D/example_1_int_in_2_out.py", "1D"
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1D/example_1_int_in_2_out_repeats.py", "1D"
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1D/example_1_cat_in_2_out_repeats.py", "1D"
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1D/example_3_cat_in_2_out.py", "3D"
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_2D/example_2_cat_in_4_out_repeats.py", "1D"
    )

    # todo, enable
    # convert_example_to_jupyter_notebook(
    #     "/workspaces/bencher/bencher/example/example_composable_container_video.py",
    #     "Media",
    # )
