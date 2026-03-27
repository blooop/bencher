| Metric | Value |
|--------|-------|
| Total tests | 974 |
| Total time | 82.90s |
| Mean | 0.0851s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.272 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.267 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.790 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.880 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.978 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.057 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.992 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.853 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.815 |
| `test.test_bencher.TestBencher::test_combinations` | 0.790 |

</details>