import unittest
from hypothesis import given, strategies as st  # pylint: disable=unused-import
import pytest
from bencher.variables.inputs import IntSweep, EnumSweep, StringSweep, BoolSweep, FloatSweep
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.results import ResultVar
from enum import auto
from strenum import StrEnum


class TestVarSweeps(unittest.TestCase):
    def test_int_sweep_01(self):
        int_sweep = IntSweep(bounds=[0, 1])
        self.assertEqual(int_sweep.default, 0)
        self.assertListEqual(int_sweep.values(), [0, 1])

    def test_int_sweep_06(self):
        int_sweep = IntSweep(bounds=[0, 6])
        self.assertEqual(int_sweep.default, 0)
        self.assertListEqual(int_sweep.values(), [0, 1, 2, 3, 4, 5, 6])

    def test_int_sweep_06_debug_sampes(self):
        int_sweep = IntSweep(bounds=[0, 6])
        self.assertEqual(int_sweep.default, 0)
        self.assertListEqual(int_sweep.values(), [0, 1, 2, 3, 4, 5, 6])

    def test_int_sweep_10_debug_sampes(self):
        int_sweep = IntSweep(bounds=[0, 10])
        self.assertEqual(int_sweep.default, 0)
        self.assertListEqual(int_sweep.values(), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_int_sweep_10_with_values_(self):
        int_sweep = IntSweep(bounds=[0, 10])
        self.assertEqual(int_sweep.default, 0)
        self.assertListEqual(int_sweep.values(), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertListEqual(int_sweep.with_samples(3).values(), [0, 5, 10])

    def test_int_sweep_level_10_with_values_(self):
        int_sweep = IntSweep(bounds=[0, 10])
        self.assertListEqual(int_sweep.with_level(1).values(), [0])
        self.assertListEqual(int_sweep.with_level(2).values(), [0, 10])
        self.assertListEqual(int_sweep.with_level(3).values(), [0, 5, 10])
        self.assertListEqual(int_sweep.with_level(4).values(), [0, 2, 5, 7, 10])
        self.assertListEqual(int_sweep.with_level(5).values(), [0, 1, 2, 3, 5, 6, 7, 8, 10])
        self.assertListEqual(int_sweep.with_level(6).values(), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_int_sweep_level_10_with_values_and_step(self):
        int_sweep = IntSweep(bounds=[0, 10], step=2, samples=4)
        self.assertListEqual(int_sweep.with_level(1).values(), [0])
        self.assertListEqual(int_sweep.with_level(2).values(), [0, 10])
        self.assertListEqual(int_sweep.with_level(3).values(), [0, 5, 10])
        self.assertListEqual(int_sweep.with_level(4).values(), [0, 2, 5, 7, 10])
        self.assertListEqual(int_sweep.with_level(5).values(), [0, 1, 2, 3, 5, 6, 7, 8, 10])
        self.assertListEqual(int_sweep.with_level(6).values(), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_int_sweep_level_1000_with_values_(self):
        int_sweep = IntSweep(default=100, bounds=[100, 1000])
        self.assertListEqual(int_sweep.with_level(1).values(), [100])
        self.assertListEqual(int_sweep.with_level(2).values(), [100, 1000])
        self.assertListEqual(int_sweep.with_level(3).values(), [100, 550, 1000])
        self.assertListEqual(int_sweep.with_level(4).values(), [100, 325, 550, 775, 1000])
        self.assertListEqual(
            int_sweep.with_level(5).values(), [100, 212, 325, 437, 550, 662, 775, 887, 1000]
        )
        self.assertListEqual(
            int_sweep.with_level(6).values(),
            [100, 156, 212, 268, 325, 381, 437, 493, 550, 606, 662, 718, 775, 831, 887, 943, 1000],
        )

    def test_float_sweep(self):
        float_sweep = FloatSweep(bounds=[0, 1])

        self.assertListEqual(list(float_sweep.with_level(1).values()), [0.0])
        self.assertListEqual(list(float_sweep.with_level(2).values()), [0.0, 1.0])
        self.assertListEqual(list(float_sweep.with_level(3).values()), [0.0, 0.5, 1.0])
        self.assertListEqual(list(float_sweep.with_level(4).values()), [0.0, 0.25, 0.5, 0.75, 1.0])

    def test_float_sweep_with_step(self):
        float_sweep = FloatSweep(bounds=[0, 1], step=0.01)

        self.assertListEqual(list(float_sweep.with_level(1).values()), [0.0])
        self.assertListEqual(list(float_sweep.with_level(2).values()), [0.0, 1.0])
        self.assertListEqual(list(float_sweep.with_level(3).values()), [0.0, 0.5, 1.0])
        self.assertListEqual(list(float_sweep.with_level(4).values()), [0.0, 0.25, 0.5, 0.75, 1.0])

    def test_float_step(self):
        float_sweep = FloatSweep(bounds=[0, 1], step=0.1)

        self.assertListEqual(
            list(float_sweep.values()),
            [
                0.0,
                0.1,
                0.2,
                0.30000000000000004,
                0.4,
                0.5,
                0.6000000000000001,
                0.7000000000000001,
                0.8,
                0.9,
            ],
        )

        float_sweep2 = FloatSweep(bounds=[0, 0.9], step=0.1)
        # note that it does not return the upper bound of 0.9 even though it a multiple of 0.1
        self.assertListEqual(
            list(float_sweep2.values()),
            [
                0.0,
                0.1,
                0.2,
                0.30000000000000004,
                0.4,
                0.5,
                0.6000000000000001,
                0.7000000000000001,
                0.8,
            ],
        )

    def test_enum_sweep_level(self):
        class Enum1(StrEnum):
            VAL1 = auto()
            VAL2 = auto()
            VAL3 = auto()
            VAL4 = auto()

        enum_sweep = EnumSweep(Enum1)

        self.assertListEqual(enum_sweep.with_level(1).values(), [Enum1.VAL1])

        self.assertListEqual(enum_sweep.with_level(2).values(), [Enum1.VAL1, Enum1.VAL4])

        self.assertListEqual(
            enum_sweep.with_level(3).values(), [Enum1.VAL1, Enum1.VAL2, Enum1.VAL4]
        )
        self.assertListEqual(
            enum_sweep.with_level(4).values(), [Enum1.VAL1, Enum1.VAL2, Enum1.VAL3, Enum1.VAL4]
        )
        self.assertListEqual(
            enum_sweep.with_level(5).values(), [Enum1.VAL1, Enum1.VAL2, Enum1.VAL3, Enum1.VAL4]
        )

    def test_bool_default(self) -> None:
        bool_sweep_true = BoolSweep(default=True)
        self.assertTrue(bool_sweep_true.default)

        bool_sweep_false = BoolSweep(default=False)
        self.assertFalse(bool_sweep_false.default)

    def test_bool_sweep_level(self):
        bool_sweep = BoolSweep()

        self.assertListEqual(bool_sweep.with_level(1).values(), [True])
        self.assertListEqual(bool_sweep.with_level(2).values(), [True, False])
        self.assertListEqual(bool_sweep.with_level(3).values(), [True, False])

    def test_string_sweep_level(self):
        string_sweep = StringSweep(["VAL1", "VAL2", "VAL3", "VAL4"])
        self.assertListEqual(string_sweep.with_level(1).values(), ["VAL1"])
        self.assertListEqual(string_sweep.with_level(2).values(), ["VAL1", "VAL4"])
        self.assertListEqual(string_sweep.with_level(3).values(), ["VAL1", "VAL2", "VAL4"])
        self.assertListEqual(string_sweep.with_level(4).values(), ["VAL1", "VAL2", "VAL3", "VAL4"])
        self.assertListEqual(string_sweep.with_level(5).values(), ["VAL1", "VAL2", "VAL3", "VAL4"])

    @given(st.integers(min_value=1, max_value=10))
    def test_int_sweep_samples(self, samples):
        int_sweep = IntSweep(bounds=[0, 10], samples=samples)
        self.assertEqual(int_sweep.default, 0)
        self.assertEqual(len(int_sweep.values()), samples)

    @pytest.mark.skip
    @given(st.integers(min_value=1, max_value=10))
    def test_int_sweep_samples_all(self, samples):
        int_sweep = IntSweep(bounds=[0, 10], samples=samples)
        self.assertEqual(int_sweep.default, 0)
        self.assertEqual(len(int_sweep.values()), samples)

    def test_sweep_bounds_property(self):
        fs = FloatSweep(bounds=(0, 1))
        self.assertEqual(fs.sweep_bounds, (0, 1))
        self.assertIsNone(fs.bounds)

        int_sw = IntSweep(bounds=(0, 10))
        self.assertEqual(int_sw.sweep_bounds, (0, 10))
        self.assertIsNone(int_sw.bounds)

    def test_float_sweep_out_of_bounds(self):
        class Cfg(ParametrizedSweep):
            theta = FloatSweep(default=0.5, bounds=(0, 1), samples=3)
            result = ResultVar()

        cfg = Cfg()
        cfg.update_params_from_kwargs(theta=1.5)
        self.assertEqual(cfg.theta, 1.5)

        cfg.update_params_from_kwargs(theta=-0.5)
        self.assertEqual(cfg.theta, -0.5)

    def test_int_sweep_out_of_bounds(self):
        class Cfg(ParametrizedSweep):
            count = IntSweep(default=3, bounds=(0, 10))
            result = ResultVar()

        cfg = Cfg()
        cfg.update_params_from_kwargs(count=15)
        self.assertEqual(cfg.count, 15)

        cfg.update_params_from_kwargs(count=-5)
        self.assertEqual(cfg.count, -5)
