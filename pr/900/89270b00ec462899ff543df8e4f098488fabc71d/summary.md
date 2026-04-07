| Metric | Value |
|--------|-------|
| Total tests | 1223 |
| Total time | 107.96s |
| Mean | 0.0883s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.370 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.933 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.155 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.300 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.188 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.059 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.512 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.257 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.227 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.925 |

</details>