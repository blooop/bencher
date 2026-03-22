| Metric | Value |
|--------|-------|
| Total tests | 893 |
| Total time | 202.44s |
| Mean | 0.2267s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 40.325 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool-units='ratio', doc='test']` | 8.116 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultReference-doc='test']` | 8.114 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVar-units='ul', doc='test']` | 8.108 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultString-doc='test']` | 8.070 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_bench_cfg_hash_stable_across_processes` | 8.054 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultPath-doc='test']` | 8.037 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultContainer-doc='test']` | 8.032 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVec-size=3, units='ul', doc='test']` | 8.010 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultHmap-doc='test']` | 8.002 |

</details>