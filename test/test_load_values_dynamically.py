import bencher as bch
import param


class DynCfg2(param.Parameterized):
    state_id = bch.StringSweep.dynamic(doc="Dynamic test")


def test_load_values_dynamically_name():
    cfg = DynCfg2()
    values = ["one", "two", "three"]
    cfg.param.state_id.load_values_dynamically(values)
    assert list(cfg.param.state_id.objects) == values
    assert cfg.state_id == "one"


def test_backward_compat_wrappers():
    cfg = DynCfg2()
    vals = ["x", "y"]
    cfg.param.state_id.update_options(vals)
    assert list(cfg.param.state_id.objects) == vals
    cfg.param.state_id.update_objects(["a"])  # second wrapper
    assert list(cfg.param.state_id.objects) == ["a"]
