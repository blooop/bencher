import nbformat as nbf
from pathlib import Path


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

    nb["cells"] = [
        nbf.v4.new_markdown_cell(text),
        nbf.v4.new_code_cell(code),
        nbf.v4.new_code_cell(code_results),
    ]
    output_path = Path(f"docs/reference/{output_path}/ex_{title}.ipynb")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Add a newline character at the end to ensure proper end-of-file
    notebook_content = nbf.writes(nb) + "\n"
    output_path.write_text(notebook_content, encoding="utf-8")


if __name__ == "__main__":
    # Examples with different numbers of categorical variables in increasing order
    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0_float/example_0_cat_in_2_out.py",
        "inputs_0_float",
        repeats=100,
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0_float/example_1_cat_in_2_out.py",
        "inputs_0_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0_float/example_2_cat_in_2_out.py",
        "inputs_0_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0_float/example_3_cat_in_2_out.py",
        "inputs_0_float",
    )

    # Examples with 1 float input plus varying categorical inputs
    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1_float/example_1_float_0_cat_in_2_out.py",
        "inputs_1_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1_float/example_1_float_1_cat_in_2_out.py",
        "inputs_1_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1_float/example_1_float_2_cat_in_2_out.py",
        "inputs_1_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_1_float/example_1_float_3_cat_in_2_out.py",
        "inputs_1_float",
    )

    # Example with 2 float inputs plus categorical inputs
    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_2_float/example_2_float_3_cat_in_2_out.py",
        "inputs_2_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_2_float/example_2_float_2_cat_in_2_out.py",
        "inputs_2_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_2_float/example_2_float_1_cat_in_2_out.py",
        "inputs_2_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_2_float/example_2_float_0_cat_in_2_out.py",
        "inputs_2_float",
    )

    # Examples with 3 float inputs plus categorical inputs
    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_3_float/example_3_float_3_cat_in_2_out.py",
        "inputs_3_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_3_float/example_3_float_2_cat_in_2_out.py",
        "inputs_3_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_3_float/example_3_float_1_cat_in_2_out.py",
        "inputs_3_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_3_float/example_3_float_0_cat_in_2_out.py",
        "inputs_3_float",
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0D/example_0_in_1_out.py", "0D", repeats=100
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/inputs_0D/example_0_in_2_out.py", "0D", repeats=100
    )

    # Other 1D examples
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
        "/workspaces/bencher/bencher/example/inputs_2D/example_2_cat_in_4_out_repeats.py", "1D"
    )

    convert_example_to_jupyter_notebook(
        "/workspaces/bencher/bencher/example/example_levels.py", "Levels"
    )

    # todo, enable
    # convert_example_to_jupyter_notebook(
    #     "/workspaces/bencher/bencher/example/example_composable_container_video.py",
    #     "Media",
    # )
