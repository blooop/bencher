| Metric | Value |
|--------|-------|
| Total tests | 1018 |
| Total time | 98.95s |
| Mean | 0.0972s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.640 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.902 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.809 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.920 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.888 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.341 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.298 |
| `test.test_bencher.TestBencher::test_combinations` | 1.080 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.002 |
| `test.test_generated_examples::test_generated_example[performance/perf_self_benchmark.py]` | 0.953 |

</details>