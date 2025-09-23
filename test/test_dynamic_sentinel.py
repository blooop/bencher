import bencher as bch
import param


class DynCfg(param.Parameterized):
    state_id = bch.StringSweep.dynamic(doc="State selector placeholder")


class DynCfgCustomPH(param.Parameterized):
    state_id = bch.StringSweep.dynamic(doc="State selector placeholder", placeholder="Pick one")


def test_dynamic_placeholder_initial():
    cfg = DynCfg()
    # Initially one placeholder value
    assert len(cfg.param.state_id.objects) == 1
    # The placeholder is the only value, and should match what was set in StringSweep.dynamic()
    assert cfg.state_id == cfg.param.state_id.objects[0]


def test_dynamic_placeholder_replaced():
    cfg = DynCfg()
    placeholder = cfg.param.state_id.objects[0]
    new_vals = ["idle", "moving", "error"]
    cfg.param.state_id.load_values_dynamically(new_vals)
    assert list(cfg.param.state_id.objects) == new_vals
    # Default becomes first entry
    assert cfg.state_id == "idle"
    # Placeholder should not remain in the new values
    assert placeholder not in new_vals


def test_dynamic_custom_placeholder():
    cfg = DynCfgCustomPH()
    assert cfg.param.state_id.objects == ["Pick one"]
    assert cfg.state_id == "Pick one"
