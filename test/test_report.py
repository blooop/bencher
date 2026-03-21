import unittest
import bencher as bn
from bencher.example.example_floats2D import example_floats2D


class TestReport(unittest.TestCase):
    """The purpose of this test class is to run the example problems to make sure they don't crash.  The bencher logic is tested in the other test files test_bencher.py and test_vars.py"""

    def test_example_floats2D_report(self) -> None:
        example_floats2D(bn.BenchRunCfg(level=2)).report.save()
