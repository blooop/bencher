| Metric | Value |
|--------|-------|
| Total tests | 974 |
| Total time | 87.51s |
| Mean | 0.0898s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.532 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.532 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.995 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.921 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.138 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.065 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 0.956 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 0.926 |
| `test.test_bencher.TestBencher::test_combinations` | 0.919 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.887 |

</details>