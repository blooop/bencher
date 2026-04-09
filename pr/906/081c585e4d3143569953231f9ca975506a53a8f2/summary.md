| Metric | Value |
|--------|-------|
| Total tests | 1254 |
| Total time | 107.43s |
| Mean | 0.0857s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.140 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.226 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.925 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.048 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.990 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.789 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.430 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.019 |
| `test.test_bench_runner.TestBenchRunner::test_bench_reuse_report_cleared` | 0.979 |
| `test.test_bencher.TestBencher::test_combinations` | 0.908 |

</details>