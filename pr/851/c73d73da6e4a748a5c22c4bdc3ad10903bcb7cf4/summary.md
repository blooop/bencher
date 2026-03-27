| Metric | Value |
|--------|-------|
| Total tests | 974 |
| Total time | 83.38s |
| Mean | 0.0856s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.335 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.252 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.860 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.842 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.986 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.086 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.011 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.874 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.854 |
| `test.test_bencher.TestBencher::test_combinations` | 0.795 |

</details>