from pathlib import Path

import pytest

import bencher as bch


EXAMPLE_YAML = (
    Path(__file__).resolve().parent.parent / "bencher" / "example" / "example_yaml_sweep.yaml"
)


def test_yaml_sweep_reads_yaml_values():
    sweep = bch.YamlSweep(EXAMPLE_YAML)
    values = sweep.values()
    keys = sweep.keys()

    assert keys == ["baseline", "extended", "heavy"]
    assert values[0].value["iterations"] == 10
    assert values[1].value["learning_rate"] == 0.05
    assert sweep.items()[2][0] == "heavy"
    assert sweep.items()[2][1].key == "heavy"


def test_yaml_sweep_sampling_respects_requested_samples():
    sweep = bch.YamlSweep(EXAMPLE_YAML, samples=2)
    assert sweep.keys() == ["baseline", "heavy"]
    assert sweep.values()[0].value["description"].startswith("Baseline")


def test_yaml_sweep_key_lookup_and_default():
    sweep = bch.YamlSweep(EXAMPLE_YAML, default_key="extended")
    items = dict(sweep.items())
    extended_value = items["extended"]

    assert sweep.default is extended_value
    assert sweep.default_key == "extended"
    assert sweep.key_for_value(extended_value) == "extended"
    assert extended_value.key == "extended"


def test_yaml_sweep_missing_file(tmp_path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        bch.YamlSweep(missing)


def test_yaml_sweep_requires_mapping(tmp_path):
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ValueError):
        bch.YamlSweep(invalid)
