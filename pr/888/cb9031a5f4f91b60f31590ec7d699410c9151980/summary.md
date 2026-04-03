| Metric | Value |
|--------|-------|
| Total tests | 1181 |
| Total time | 84.83s |
| Mean | 0.0718s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.156 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.638 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.233 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.434 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.416 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.145 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.190 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.048 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.832 |
| `test.test_file_server.TestFileServer::test_create_server` | 0.808 |

</details>