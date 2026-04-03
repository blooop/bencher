| Metric | Value |
|--------|-------|
| Total tests | 1175 |
| Total time | 104.41s |
| Mean | 0.0889s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.269 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.858 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.059 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.199 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.798 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.694 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.572 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.439 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.245 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.181 |

</details>