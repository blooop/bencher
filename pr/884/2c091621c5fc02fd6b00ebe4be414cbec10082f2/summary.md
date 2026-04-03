| Metric | Value |
|--------|-------|
| Total tests | 1180 |
| Total time | 101.82s |
| Mean | 0.0863s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.326 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.170 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.857 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.106 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.020 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.786 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.480 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.028 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.967 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.930 |

</details>