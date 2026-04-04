| Metric | Value |
|--------|-------|
| Total tests | 1204 |
| Total time | 105.31s |
| Mean | 0.0875s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.045 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.116 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.832 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.124 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.043 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.802 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.423 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.053 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.048 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.943 |

</details>