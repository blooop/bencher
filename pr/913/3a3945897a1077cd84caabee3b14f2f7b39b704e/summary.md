| Metric | Value |
|--------|-------|
| Total tests | 1297 |
| Total time | 105.87s |
| Mean | 0.0816s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.293 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.231 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.840 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.027 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.783 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.596 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.330 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.316 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.263 |
| `test.test_bench_runner_copy.TestPerIterationIsolation::test_level_repeats_combinations` | 1.066 |

</details>