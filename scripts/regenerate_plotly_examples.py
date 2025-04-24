#!/usr/bin/env python3
"""
Generate Plotly-specific examples to ensure they render correctly in Sphinx docs.
This script regenerates examples that use Plotly visualizations with proper configuration.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import the generate_examples module
parent_dir = str(Path(__file__).parent.parent.parent.absolute())
sys.path.append(parent_dir)

# Import needs to be at the top level to avoid E402 linting errors
from bencher.example.meta.generate_examples import convert_example_to_jupyter_notebook  # noqa: E402

# These examples use 3D plots with Plotly
PLOTLY_EXAMPLES = [
    # The pareto example already uses Plotly backend
    "/workspaces/bencher/bencher/example/example_pareto.py",
    # Surface and volume examples
    "/workspaces/bencher/bencher/example/inputs_2_float/example_2_float_3_cat_in_2_out.py",
    "/workspaces/bencher/bencher/example/inputs_2_float/example_2_float_0_cat_in_2_out.py",
    "/workspaces/bencher/bencher/example/examples/example_float3D.py",
]


def main():
    """
    Regenerate examples that use Plotly visualizations with proper configuration.
    """
    # Make sure we're in the right directory
    os.chdir(parent_dir)

    print("Regenerating Plotly examples with proper configuration...")

    # Convert each example using the Plotly backend
    for example in PLOTLY_EXAMPLES:
        if not os.path.exists(example):
            print(f"Warning: Example {example} does not exist, skipping.")
            continue

        # Extract folder name from example path
        path_parts = example.split("/")
        if "inputs_2_float" in example:
            output_path = "inputs_2_float"
        elif "examples" in example:
            output_path = "examples"
        else:
            # Use the directory name as the output path
            output_path = path_parts[-2]

        print(f"Converting {example} to {output_path} with Plotly backend...")
        convert_example_to_jupyter_notebook(example, output_path, backend="plotly")

    print("Done regenerating Plotly examples.")


if __name__ == "__main__":
    main()
