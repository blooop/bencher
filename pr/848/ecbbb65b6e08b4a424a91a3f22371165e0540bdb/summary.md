| Metric | Value |
|--------|-------|
| Total tests | 974 |
| Total time | 83.82s |
| Mean | 0.0861s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.667 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.196 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.827 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.926 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.890 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.031 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.889 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 0.869 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.846 |
| `test.test_bencher.TestBencher::test_combinations` | 0.823 |

</details>