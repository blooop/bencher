import bencher as bch
import param


class DummyCfg(param.Parameterized):
    state_id = bch.StringSweep(["__initialising__"], doc="Group/state identifier to render.")


def test_update_options_basic():
    cfg = DummyCfg()
    assert cfg.state_id == "__initialising__"
    assert list(cfg.param.state_id.objects) == ["__initialising__"]

    new_states = ["idle", "moving", "error"]
    # call update on underlying parameter object
    cfg.param.state_id.load_values_dynamically(new_states)

    # value should update to first element (idle)
    assert cfg.state_id == "idle"
    assert cfg.param.state_id.default == "idle"
    # class parameter also updated
    assert list(DummyCfg.param.state_id.objects) == new_states


def test_update_options_keep_current():
    cfg = DummyCfg()
    cfg.param.state_id.load_values_dynamically(["a", "b", "c"], default="b")
    assert cfg.state_id == "b"
    # now update keeping current if possible
    cfg.param.state_id.load_values_dynamically(["x", "b", "y"], keep_current_if_possible=True)
    assert cfg.state_id == "b"


def test_update_options_provided_default():
    cfg = DummyCfg()
    cfg.param.state_id.load_values_dynamically(["foo", "bar"], default="bar")
    assert cfg.state_id == "bar"
    assert cfg.param.state_id.default == "bar"


def test_update_options_invalid_default():
    cfg = DummyCfg()
    try:
        cfg.param.state_id.load_values_dynamically(["foo"], default="bar")
    except ValueError:
        pass
    else:  # pragma: no cover - ensure error raised
        assert False, "Expected ValueError for invalid default"
