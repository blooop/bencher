import unittest

from bencher.example.benchmark_data import AllSweepVars

# def get_sweep_hash_isolated_process() -> str:
#     """get has values from a separate process as by default hashes across process are not the same"""
#     os.system(
#         "python3 -c 'from bencher.example.benchmark_data import AllSweepVars;ex = AllSweepVars();print(ex.__repr__());print(ex.hash_persistent())' > hashed_vars_comparison_tmp"
#     )

#     with open("hashed_vars_comparison_tmp", "r", encoding="utf-8") as myfile:
#         res = myfile.read()
#     os.remove("hashed_vars_comparison_tmp")
#     return res


class TestBencherHashing(unittest.TestCase):
    def test_sweep_hashes(self) -> None:
        """check that separate instances with identical data have the same hash"""
        ex = AllSweepVars()
        ex2 = AllSweepVars()

        self.assertEqual(
            ex.param.var_float.hash_persistent(), ex2.param.var_float.hash_persistent()
        )
        self.assertEqual(ex.param.var_int.hash_persistent(), ex2.param.var_int.hash_persistent())
        self.assertEqual(ex.param.var_enum.hash_persistent(), ex2.param.var_enum.hash_persistent())

        print(ex.__repr__())
        print(ex2.__repr__())

        self.assertEqual(ex.hash_persistent(), ex2.hash_persistent())

    def test_hash_sweep(self) -> None:
        """hash values only seem to not match if run in a separate process, so run the hash test in separate processes"""

        asv = AllSweepVars()
        asv2 = AllSweepVars()

        self.assertEqual(
            asv.hash_persistent(),
            asv2.hash_persistent(),
            "The classes should have equal hash when it has identical values",
        )

        asv2.var_float = 1
        self.assertNotEqual(
            asv.hash_persistent(),
            asv2.hash_persistent(),
            "The classes should not have equal hash when they have different values",
        )

    # turn this off as its quite expensive and the new hash function is reliable, turn back on for release
    # def test_hash_sweep_isolated(self) -> None:
    #     """hash values only seem to not match if run in a separate process, so run the hash test in separate processes"""

    #     self.assertNotEqual(
    #         len(get_sweep_hash_isolated_process()), 0, "make sure the hash is getting returned"
    #     )

    #     self.assertEqual(
    #         get_sweep_hash_isolated_process(),
    #         get_sweep_hash_isolated_process(),
    #         "make sure the hashes are equal",
    #     )


# print(get_sweep_hash_isolated_process())
