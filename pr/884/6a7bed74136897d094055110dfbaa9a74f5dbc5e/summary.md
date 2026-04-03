| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 96.51s |
| Mean | 0.0825s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.979 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.547 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.601 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.355 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.957 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.879 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.214 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.008 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.922 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.888 |

</details>