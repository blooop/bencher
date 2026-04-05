| Metric | Value |
|--------|-------|
| Total tests | 1212 |
| Total time | 106.44s |
| Mean | 0.0878s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.858 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.266 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.840 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.154 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.997 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.870 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.535 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.067 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.037 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.916 |

</details>