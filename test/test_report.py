import unittest
import bencher as bn
from bencher.example.example_simple_float import example_simple_float


class TestReport(unittest.TestCase):
    """The purpose of this test class is to run the example problems to make sure they don't crash.  The bencher logic is tested in the other test files test_bencher.py and test_vars.py"""

    def test_example_report(self) -> None:
        example_simple_float(bn.BenchRunCfg(level=2)).report.save()
