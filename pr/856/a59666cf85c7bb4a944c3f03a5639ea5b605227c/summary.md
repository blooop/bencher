| Metric | Value |
|--------|-------|
| Total tests | 1018 |
| Total time | 99.04s |
| Mean | 0.0973s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.535 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.976 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.794 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.964 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.851 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.347 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.278 |
| `test.test_bencher.TestBencher::test_combinations` | 1.089 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.019 |
| `test.test_generated_examples::test_generated_example[performance/perf_self_benchmark.py]` | 0.946 |

</details>