| Metric | Value |
|--------|-------|
| Total tests | 1185 |
| Total time | 103.43s |
| Mean | 0.0873s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.979 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.148 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.929 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.164 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.045 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.930 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.513 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.336 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 1.006 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.954 |

</details>