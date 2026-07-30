"""A Parameter that never got a name from param's metaclass must be rejected.

param assigns ``Parameter.name`` in the metaclass of the class that *declares* the
parameter.  A parameter declared on a plain (non-Parameterized) mixin is therefore
picked up by param's MRO scan when the mixin is combined into a real
``ParametrizedSweep``, but keeps ``name=None`` -- and used to resolve successfully,
failing far away where ``.name`` keys the dataset variable or the result dict.

The no-false-positive tests matter as much as the rejection ones: a Parameter
passed as an object need not correspond to any attribute on the worker, because
``bn.box()`` and ``bn.sweep()`` build named copies that live outside the class
namespace.
"""

import param
import pytest

import bencher as bn


class PlainResultMixin:
    """A plain mixin declaring a result var -- the trap. Not Parameterized."""

    unnamed_result = bn.ResultFloat()


class PlainInputMixin:
    """A plain mixin declaring a sweep var -- the same trap on the input side."""

    unnamed_input = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])


class ProperResultMixin(bn.ParametrizedSweep):
    """The same mixin done correctly: param names the variable."""

    named_result = bn.ResultFloat()


class Base(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])
    y = bn.ResultFloat()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = float(self.x)
        return self.get_results_values_as_dict()


class BadResult(PlainResultMixin, Base):
    pass


class BadInput(PlainInputMixin, Base):
    pass


class Good(ProperResultMixin, Base):
    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = float(self.x)
        self.named_result = float(self.x) * 2.0
        return self.get_results_values_as_dict()


def test_plain_mixin_result_var_is_rejected():
    """The trap this guard exists for, on the result side."""
    with pytest.raises(TypeError) as exc:
        BadResult().to_bench().plot_sweep(
            input_vars=["x"], result_vars=["y", "unnamed_result"], auto_plot=False
        )
    msg = str(exc.value)
    assert "unnamed_result" in msg
    assert "param.Parameterized" in msg
    assert "ParametrizedSweep" in msg


def test_plain_mixin_input_var_is_rejected():
    """Same trap on the input side, where it corrupts coordinate identity."""
    with pytest.raises(TypeError) as exc:
        BadInput().to_bench().plot_sweep(
            input_vars=["unnamed_input"], result_vars=["y"], auto_plot=False
        )
    assert "unnamed_input" in str(exc.value)


def test_parameterized_mixin_still_works():
    """The corrected composition must run and name its columns."""
    res = (
        Good()
        .to_bench()
        .plot_sweep(input_vars=["x"], result_vars=["y", "named_result"], auto_plot=False)
    )
    assert set(res.to_dataset().data_vars) == {"y", "named_result"}


def test_unknown_name_still_raises_key_error():
    """The new check must not shadow the missing-variable error."""
    with pytest.raises(KeyError) as exc:
        Base().to_bench().plot_sweep(input_vars=["nope"], result_vars=["y"], auto_plot=False)
    assert "Available parameters" in str(exc.value)


@pytest.mark.parametrize(
    "make_input",
    [
        pytest.param(lambda: bn.box("x", 0.5, 0.1), id="box"),
        pytest.param(lambda: bn.sweep("x", bounds=(0.0, 1.0)), id="sweep_by_name"),
        pytest.param(lambda: bn.sweep(Base.param.x, samples=3), id="sweep_by_object"),
        pytest.param(lambda: Base.param.x, id="bare_param_object"),
        pytest.param(lambda: "x", id="bare_string"),
    ],
)
def test_no_false_positives_for_legitimate_forms(make_input):
    """Every accepted input-var form must survive the guard.

    ``box()`` and the object forms build Parameters that are named but absent from
    the class namespace, so a key-equality check on this path would reject them.
    """
    res = (
        Base().to_bench().plot_sweep(input_vars=[make_input()], result_vars=["y"], auto_plot=False)
    )
    assert "y" in res.to_dataset().data_vars


def test_dynamically_built_worker_is_not_penalised():
    """A worker built with type() still goes through param's metaclass."""
    dyn = type("Dyn", (Base,), {"extra": bn.ResultFloat()})
    res = dyn().to_bench().plot_sweep(input_vars=["x"], result_vars=["y"], auto_plot=False)
    assert "y" in res.to_dataset().data_vars
    assert dyn.param.objects(instance=False)["extra"].name == "extra"


def test_the_old_symptom_is_unreachable():
    """No config may reach sampling with a None-named result variable.

    Read the Parameter out of ``__dict__``: from param 2.4 the descriptor's
    ``__get__`` raises for an unnamed Parameter, so plain attribute access cannot
    be used to inspect the very state under test.
    """
    assert PlainResultMixin.__dict__["unnamed_result"].name is None, (
        "premise of this whole guard: a plain mixin's Parameter has no name"
    )
    with pytest.raises(TypeError):
        BadResult().to_bench().plot_sweep(
            input_vars=["x"], result_vars=["unnamed_result"], auto_plot=False
        )


def test_object_path_rejects_a_none_named_parameter():
    """Passing the unnamed Parameter as an object is caught too."""
    with pytest.raises(TypeError) as exc:
        Base().to_bench().plot_sweep(
            input_vars=["x"],
            result_vars=[PlainResultMixin.__dict__["unnamed_result"]],
            auto_plot=False,
        )
    assert "param.Parameterized" in str(exc.value)


def test_premise_holds_for_param_directly():
    """Guard against param changing this behaviour under us."""

    class Mixin:
        v = param.Number(default=1.0)

    class Combined(Mixin, param.Parameterized):
        pass

    assert "v" in Combined.param.objects(instance=False)
    assert Combined.param.objects(instance=False)["v"].name is None
