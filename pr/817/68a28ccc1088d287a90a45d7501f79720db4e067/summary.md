| Metric | Value |
|--------|-------|
| Total tests | 903 |
| Total time | 193.82s |
| Mean | 0.2146s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 39.024 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVec-size=3, units='ul', doc='test']` | 7.731 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultContainer-doc='test']` | 7.577 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVar-units='ul', doc='test']` | 7.565 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_bench_cfg_hash_stable_across_processes` | 7.540 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool-units='ratio', doc='test']` | 7.523 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultString-doc='test']` | 7.507 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultHmap-doc='test']` | 7.496 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultImage-doc='test']` | 7.466 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultPath-doc='test']` | 7.465 |

</details>