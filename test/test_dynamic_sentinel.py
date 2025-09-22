import bencher as bch
import param


class DynCfg(param.Parameterized):
    state_id = bch.StringSweep.dynamic(doc="State selector placeholder")


def test_dynamic_placeholder_initial():
    cfg = DynCfg()
    # Initially one placeholder value
    assert len(cfg.param.state_id.objects) == 1
    assert cfg.state_id == str(bch.LoadValuesDynamically)


def test_dynamic_placeholder_replaced():
    cfg = DynCfg()
    new_vals = ["idle", "moving", "error"]
    cfg.param.state_id.update_options(new_vals)
    assert list(cfg.param.state_id.objects) == new_vals
    # Default becomes first entry
    assert cfg.state_id == "idle"
    # Sentinel should not remain
    assert all(v != str(bch.LoadValuesDynamically) for v in new_vals)
