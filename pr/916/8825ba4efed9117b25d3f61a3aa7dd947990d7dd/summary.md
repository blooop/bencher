| Metric | Value |
|--------|-------|
| Total tests | 1305 |
| Total time | 111.99s |
| Mean | 0.0858s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.350 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.175 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.249 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.090 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.042 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.828 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.455 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.402 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.337 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.004 |

</details>