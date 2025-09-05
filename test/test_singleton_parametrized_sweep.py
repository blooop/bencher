import pytest
from bencher.variables.singleton_parametrized_sweep import SingletonParametrizedSweep


# Ensure singleton cache is cleared before each test for isolation
@pytest.fixture(autouse=True)
def clear_singleton_cache():
    SingletonParametrizedSweep._instances.clear()


class ChildA(SingletonParametrizedSweep):
    def __init__(self, value=1):
        super().__init__()
        if not hasattr(self, "init_count"):
            self.init_count = 1
            self.value = value


class ChildB(SingletonParametrizedSweep):
    def __init__(self, value=2):
        super().__init__()
        if not hasattr(self, "init_count"):
            self.init_count = 1
            self.value = value


def test_singleton_per_child():
    a1 = ChildA()
    a2 = ChildA()
    b1 = ChildB()
    b2 = ChildB()
    assert a1 is a2, "ChildA should return the same instance"
    assert b1 is b2, "ChildB should return the same instance"
    assert a1 is not b1, "ChildA and ChildB should have different singleton instances"


def test_singleton_init_only_once():
    a1 = ChildA()
    a2 = ChildA()
    assert a1.init_count == 1, "__init__ should only run once for ChildA"
    b1 = ChildB()
    b2 = ChildB()
    assert b1.init_count == 1, "__init__ should only run once for ChildB"


def test_singleton_value_persistence():
    a1 = ChildA(value=10)
    a2 = ChildA(value=20)
    assert a1.value == 10, "Value should be set only on first init and persist"
    assert a2.value == 10, "Subsequent inits should not overwrite value"
