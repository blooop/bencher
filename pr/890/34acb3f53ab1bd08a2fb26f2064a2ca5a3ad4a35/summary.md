| Metric | Value |
|--------|-------|
| Total tests | 1185 |
| Total time | 101.49s |
| Mean | 0.0856s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.591 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.226 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.805 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.103 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.038 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.780 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.385 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.028 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.996 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.985 |

</details>