| Metric | Value |
|--------|-------|
| Total tests | 1019 |
| Total time | 101.63s |
| Mean | 0.0997s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.808 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.261 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.822 |
| `test.test_generated_examples::test_generated_example[advanced/advanced_cartesian_animation.py]` | 2.907 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.896 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.840 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.300 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.272 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.220 |
| `test.test_bencher.TestBencher::test_combinations` | 1.075 |

</details>