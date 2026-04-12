| Metric | Value |
|--------|-------|
| Total tests | 1255 |
| Total time | 102.75s |
| Mean | 0.0819s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.861 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.163 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.732 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.027 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.901 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.713 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.322 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.005 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.879 |
| `test.test_bencher.TestBencher::test_combinations` | 0.866 |

</details>