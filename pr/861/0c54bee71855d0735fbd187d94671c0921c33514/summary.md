| Metric | Value |
|--------|-------|
| Total tests | 1019 |
| Total time | 102.44s |
| Mean | 0.1005s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.969 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.071 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.786 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.761 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.896 |
| `test.test_generated_examples::test_generated_example[advanced/advanced_cartesian_animation.py]` | 2.813 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.469 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.291 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.273 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.176 |

</details>