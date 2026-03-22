| Metric | Value |
|--------|-------|
| Total tests | 906 |
| Total time | 193.82s |
| Mean | 0.2139s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 37.907 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_bench_cfg_hash_stable_across_processes` | 7.797 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVolume-doc='test']` | 7.779 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultContainer-doc='test']` | 7.680 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultReference-doc='test']` | 7.663 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultDataSet-doc='test']` | 7.660 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVec-size=3, units='ul', doc='test']` | 7.633 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultString-doc='test']` | 7.617 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool-units='ratio', doc='test']` | 7.577 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVar-units='ul', doc='test']` | 7.522 |

</details>