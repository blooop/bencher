| Metric | Value |
|--------|-------|
| Total tests | 1254 |
| Total time | 109.90s |
| Mean | 0.0876s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.595 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.344 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.037 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.168 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.083 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.861 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.448 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.050 |
| `test.test_bench_runner.TestBenchRunner::test_bench_reuse_report_cleared` | 1.017 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.938 |

</details>