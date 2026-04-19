| Metric | Value |
|--------|-------|
| Total tests | 1313 |
| Total time | 115.79s |
| Mean | 0.0882s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.320 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.082 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.706 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.239 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.193 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.946 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.507 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.275 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.191 |
| `test.test_generated_examples::test_generated_example[2_float/over_time/example_sweep_2_float_2_cat_over_time.py]` | 1.109 |

</details>