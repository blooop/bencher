| Metric | Value |
|--------|-------|
| Total tests | 2278 |
| Total time | 144.92s |
| Mean | 0.0636s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.246 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.161 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.950 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.713 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.462 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.229 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.984 |
| `test.test_parallel_data_integrity.TestParallelBenchWithCache::test_parallel_repeated_runs_identical` | 2.923 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.921 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.738 |

</details>