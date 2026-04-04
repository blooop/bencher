"""Meta-generator: YAML sweep examples.

Copies the hand-written YAML sweep examples and their data files into the
generated directory so they are included in the documentation build.
"""

import shutil
from pathlib import Path

import bencher as bn

from .generate_examples import GENERATED_DIR

EXAMPLE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = "yaml"

# (source_py_name, dest_py_name, yaml_data_files)
YAML_EXAMPLES = [
    ("yaml_sweep_list.py", "example_yaml_sweep_list.py", ["yaml_sweep_list.yaml"]),
    ("yaml_sweep_dict.py", "example_yaml_sweep_dict.py", ["yaml_sweep_dict.yaml"]),
]


def example_meta_yaml(run_cfg: bn.BenchRunCfg | None = None) -> None:  # pylint: disable=unused-argument
    """Copy YAML sweep examples into the generated directory."""
    dest = GENERATED_DIR / OUTPUT_DIR
    dest.mkdir(parents=True, exist_ok=True)

    for source_name, dest_name, yaml_names in YAML_EXAMPLES:
        shutil.copy2(EXAMPLE_DIR / source_name, dest / dest_name)
        for y in yaml_names:
            shutil.copy2(EXAMPLE_DIR / y, dest / y)
