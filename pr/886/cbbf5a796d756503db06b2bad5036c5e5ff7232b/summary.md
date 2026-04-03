| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 85.37s |
| Mean | 0.0730s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.050 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.696 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.248 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.470 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.444 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.237 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.218 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.131 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.053 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_1_cat_over_time_repeats.py]` | 0.930 |

</details>