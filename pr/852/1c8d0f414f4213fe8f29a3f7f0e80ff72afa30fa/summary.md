| Metric | Value |
|--------|-------|
| Total tests | 1206 |
| Total time | 89.93s |
| Mean | 0.0746s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.069 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.683 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.267 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.455 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.431 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.166 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/example_sweep_1_float_0_cat_over_time.py]` | 1.343 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.200 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.112 |
| `test.test_sample_cache.TestSampleCache::test_sample_cache_context` | 1.054 |

</details>