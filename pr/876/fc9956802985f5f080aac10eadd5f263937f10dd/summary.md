| Metric | Value |
|--------|-------|
| Total tests | 1145 |
| Total time | 105.85s |
| Mean | 0.0924s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.460 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.305 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.746 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.055 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.861 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.635 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.238 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 1.125 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.110 |
| `test.test_bencher.TestBencher::test_combinations` | 1.082 |

</details>