| Metric | Value |
|--------|-------|
| Total tests | 1019 |
| Total time | 110.73s |
| Mean | 0.1087s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.926 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.843 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.159 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.152 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.104 |
| `test.test_generated_examples::test_generated_example[advanced/advanced_cartesian_animation.py]` | 3.048 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.546 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.429 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.423 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.320 |

</details>