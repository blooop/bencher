| Metric | Value |
|--------|-------|
| Total tests | 894 |
| Total time | 182.60s |
| Mean | 0.2043s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 37.371 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVec-size=3, units='ul', doc='test']` | 7.241 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool-units='ratio', doc='test']` | 7.196 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVar-units='ul', doc='test']` | 7.192 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultHmap-doc='test']` | 7.183 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultString-doc='test']` | 7.156 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultImage-doc='test']` | 7.139 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultPath-doc='test']` | 7.134 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_bench_cfg_hash_stable_across_processes` | 7.123 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultReference-doc='test']` | 7.106 |

</details>