import bencher as bch

from bencher.example.signal_processing.digital_filter import (
    DigitalFilterAnalysis,
    example_digital_filter,
    FilterType,
    WindowFunction,
)


def test_digital_filter():
    """Test that the digital filter analysis example runs without errors."""
    # Create a simple run config with minimal repetitions
    run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 2

    # Create the benchmark
    bench = example_digital_filter(run_cfg)

    # Check that the benchmark has the expected properties
    assert isinstance(bench, bch.Bench)

    # Run a simple sweep to test functionality
    res = bench.plot_sweep(
        "test_sweep",
        input_vars=["filter_type", "filter_order"],
        result_vars=[DigitalFilterAnalysis.param.stopband_attenuation],
    )

    # Verify that we got results
    assert res is not None

    # Test different filter types
    lowpass = DigitalFilterAnalysis(
        filter_type=FilterType.low_pass, filter_order=4.0, window_function=WindowFunction.hamming
    )
    lowpass()

    highpass = DigitalFilterAnalysis(
        filter_type=FilterType.high_pass, filter_order=4.0, window_function=WindowFunction.hamming
    )
    highpass()

    # Test that filter order affects stopband attenuation
    low_order = DigitalFilterAnalysis(filter_order=2.0)
    low_order()
    high_order = DigitalFilterAnalysis(filter_order=8.0)
    high_order()

    # Higher order filters should have better stopband attenuation
    assert high_order.stopband_attenuation > low_order.stopband_attenuation

    # Test that different window functions have different passband ripple characteristics
    rectangular = DigitalFilterAnalysis(window_function=WindowFunction.rectangular)
    rectangular()
    blackman = DigitalFilterAnalysis(window_function=WindowFunction.blackman)
    blackman()

    # Blackman window should have lower passband ripple than rectangular
    assert blackman.passband_ripple < rectangular.passband_ripple
