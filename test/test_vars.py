import unittest

from bencher.example.benchmark_data import AllSweepVars


class TestBencherHashing(unittest.TestCase):
    def test_sweep_hashes(self) -> None:
        """check that separate instances with identical data have the same hash"""
        ex = AllSweepVars()
        ex2 = AllSweepVars()

        assert ex.param.var_float.hash_persistent() == ex2.param.var_float.hash_persistent()
        assert ex.param.var_int.hash_persistent() == ex2.param.var_int.hash_persistent()
        assert ex.param.var_enum.hash_persistent() == ex2.param.var_enum.hash_persistent()

        assert ex.hash_persistent() == ex2.hash_persistent()

    def test_hash_sweep(self) -> None:
        """hash values only seem to not match if run in a separate process, so run the hash test in separate processes"""

        asv = AllSweepVars()
        asv2 = AllSweepVars()

        assert asv.hash_persistent() == asv2.hash_persistent(), (
            "The classes should have equal hash when it has identical values"
        )

        asv2.var_float = 1
        assert asv.hash_persistent() != asv2.hash_persistent(), (
            "The classes should not have equal hash when they have different values"
        )
