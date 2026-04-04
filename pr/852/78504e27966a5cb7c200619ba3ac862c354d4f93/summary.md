| Metric | Value |
|--------|-------|
| Total tests | 1206 |
| Total time | 106.63s |
| Mean | 0.0884s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.095 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.190 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.933 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.144 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.048 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.909 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.516 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.062 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.998 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.962 |

</details>