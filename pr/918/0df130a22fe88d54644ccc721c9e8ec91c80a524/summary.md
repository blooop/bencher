| Metric | Value |
|--------|-------|
| Total tests | 1301 |
| Total time | 94.80s |
| Mean | 0.0729s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.787 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.760 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.598 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.485 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.389 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.240 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.685 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.541 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.038 |
| `test.test_bencher.TestBencher::test_combinations` | 0.993 |

</details>