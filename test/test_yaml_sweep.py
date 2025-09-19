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

    assert keys == ["quick", "balanced", "thorough"]
    key0, value0 = values[0]
    assert key0 == "quick"
    assert value0 == [12, 18, 27]
    assert values[0].key() == "quick"
    assert values[0].value() == [12, 18, 27]
    assert sum(values[1].value()) == 100
    assert sweep.items()[2][0] == "thorough"
    assert sweep.items()[2][1] == [15, 20, 25, 30, 35]


def test_yaml_sweep_sampling_respects_requested_samples():
    sweep = bch.YamlSweep(EXAMPLE_YAML, samples=2)
    assert sweep.keys() == ["quick", "thorough"]
    assert sweep.values()[0].value() == [12, 18, 27]


def test_yaml_sweep_key_lookup_and_default():
    sweep = bch.YamlSweep(EXAMPLE_YAML, default_key="balanced")
    items = dict(sweep.items())
    balanced_value = items["balanced"]

    assert sweep.default == "balanced"
    assert sweep.default_key == "balanced"
    assert sweep.key_for_value(sweep.default) == "balanced"
    assert sum(balanced_value) == 100


def test_yaml_sweep_missing_file(tmp_path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        bch.YamlSweep(missing)


def test_yaml_sweep_requires_mapping(tmp_path):
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ValueError):
        bch.YamlSweep(invalid)
