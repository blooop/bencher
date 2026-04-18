| Metric | Value |
|--------|-------|
| Total tests | 1297 |
| Total time | 108.01s |
| Mean | 0.0833s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.716 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.110 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.837 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.062 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.837 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.599 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.470 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.341 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.283 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_v2_signature` | 1.032 |

</details>