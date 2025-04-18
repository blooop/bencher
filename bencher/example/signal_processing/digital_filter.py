import bencher as bch
import numpy as np
from enum import auto
from strenum import StrEnum
import random


class FilterType(StrEnum):
    """Types of digital filters"""

    low_pass = auto()  # Attenuates high frequencies
    high_pass = auto()  # Attenuates low frequencies
    band_pass = auto()  # Passes a certain band of frequencies
    band_stop = auto()  # Rejects a certain band of frequencies


class WindowFunction(StrEnum):
    """Window functions for filter design"""

    rectangular = auto()  # No windowing
    hamming = auto()  # Hamming window
    hanning = auto()  # Hanning window
    blackman = auto()  # Blackman window


class DigitalFilterAnalysis(bch.ParametrizedSweep):
    """Analysis of digital filters with various parameters"""

    # Floating point variables
    cutoff_frequency = bch.FloatSweep(
        default=1000.0, bounds=[10.0, 10000.0], doc="Cutoff frequency (Hz)"
    )
    sampling_rate = bch.FloatSweep(
        default=44100.0, bounds=[8000.0, 96000.0], doc="Sampling rate (Hz)"
    )
    filter_order = bch.FloatSweep(default=4.0, bounds=[1.0, 20.0], doc="Filter order")
    transition_width = bch.FloatSweep(
        default=200.0, bounds=[10.0, 2000.0], doc="Transition width (Hz)"
    )
    center_frequency = bch.FloatSweep(
        default=2000.0, bounds=[100.0, 8000.0], doc="Center frequency for band filters (Hz)"
    )

    # Categorical variables
    filter_type = bch.EnumSweep(FilterType, default=FilterType.low_pass, doc=FilterType.__doc__)
    window_function = bch.EnumSweep(
        WindowFunction, default=WindowFunction.hamming, doc=WindowFunction.__doc__
    )
    use_frequency_warping = bch.BoolSweep(
        default=False, doc="Apply bilinear frequency warping correction"
    )

    # Result variables
    stopband_attenuation = bch.ResultVar("dB", doc="Stopband attenuation")
    passband_ripple = bch.ResultVar("dB", doc="Passband ripple")
    computational_complexity = bch.ResultVar("ops/sample", doc="Computational complexity")
    group_delay = bch.ResultVar("ms", doc="Group delay at half cutoff frequency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Round filter order to nearest integer
        filter_order = int(round(self.filter_order))

        # Calculate normalized cutoff frequency
        nyquist = self.sampling_rate / 2
        norm_cutoff = self.cutoff_frequency / nyquist
        norm_center = self.center_frequency / nyquist
        norm_transition = self.transition_width / nyquist

        # Apply frequency warping if enabled
        if self.use_frequency_warping and norm_cutoff > 0.1:
            # Bilinear transform prewarping
            norm_cutoff = (2 / np.pi) * np.arctan(np.pi * norm_cutoff / 2)
            if self.filter_type in [FilterType.band_pass, FilterType.band_stop]:
                norm_center = (2 / np.pi) * np.arctan(np.pi * norm_center / 2)

        # Calculate stopband attenuation based on filter order and window function
        # Higher order and better windows give higher attenuation
        base_attenuation = {
            WindowFunction.rectangular: 21,
            WindowFunction.hamming: 53,
            WindowFunction.hanning: 44,
            WindowFunction.blackman: 74,
        }[self.window_function]

        # Attenuation increases with filter order
        self.stopband_attenuation = base_attenuation + 6 * (filter_order - 1)

        # Add some random variation to represent implementation details
        self.stopband_attenuation *= 1 + random.uniform(-0.05, 0.05)

        # Calculate passband ripple - different window functions have different ripple characteristics
        base_ripple = {
            WindowFunction.rectangular: 0.9,
            WindowFunction.hamming: 0.2,
            WindowFunction.hanning: 0.3,
            WindowFunction.blackman: 0.1,
        }[self.window_function]

        # Ripple generally decreases with filter order but increases with cutoff frequency
        self.passband_ripple = base_ripple * (1 + 0.05 * norm_cutoff) / (1 + 0.02 * filter_order)
        self.passband_ripple *= 1 + random.uniform(-0.1, 0.1)  # Add variation

        # Computational complexity - operations per sample
        # FIR filters: roughly 2 * filter_order operations per sample
        # Different filter types have different computational needs
        if self.filter_type in [FilterType.low_pass, FilterType.high_pass]:
            self.computational_complexity = 2 * filter_order
        else:  # Band filters are more complex
            self.computational_complexity = 4 * filter_order

        # Group delay calculation - for FIR filters, group delay is N/2 samples
        # Convert to milliseconds
        self.group_delay = (filter_order / 2) * (1000 / self.sampling_rate)

        # Different filter types affect group delay differently
        if self.filter_type == FilterType.high_pass:
            # High-pass filters often have less delay at high frequencies
            self.group_delay *= 0.9
        elif self.filter_type == FilterType.band_pass:
            # Band-pass can have more delay
            self.group_delay *= 1.1
        elif self.filter_type == FilterType.band_stop:
            # Band-stop can have even more delay
            self.group_delay *= 1.2

        # Apply some noise to represent real-world variations
        self.group_delay *= 1 + random.uniform(-0.03, 0.03)

        return super().__call__()


def example_digital_filter(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Create a benchmark for the digital filter analysis"""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 5  # Multiple repeats to show statistical variations
        run_cfg.level = 3

    bench = DigitalFilterAnalysis().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Digital Filter Analysis",
        description="""## Digital Signal Processing Filter Analysis
This benchmark explores the characteristics of various digital filters with different 
parameters, filter types, and design techniques.""",
        input_vars=[
            "filter_type",
            "cutoff_frequency",
            "filter_order",
            "window_function",
            "use_frequency_warping",
            "sampling_rate",
        ],
        result_vars=[
            DigitalFilterAnalysis.param.stopband_attenuation,
            DigitalFilterAnalysis.param.passband_ripple,
            DigitalFilterAnalysis.param.computational_complexity,
            DigitalFilterAnalysis.param.group_delay,
        ],
    )

    return bench


if __name__ == "__main__":
    example_digital_filter()
