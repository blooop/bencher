| Metric | Value |
|--------|-------|
| Total tests | 1305 |
| Total time | 109.78s |
| Mean | 0.0841s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.139 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.587 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.154 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.015 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.781 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.598 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.707 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.285 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.023 |
| `test.test_bencher.TestBencher::test_combinations` | 1.014 |

</details>