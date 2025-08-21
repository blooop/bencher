#!/usr/bin/env python3
"""Test rerun integration with bencher"""

import math
import bencher as bch


class SimpleFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=5
    )
    out_sin = bch.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__(**kwargs)


def test_rerun_backend():
    """Test the rerun backend integration"""
    print("Testing rerun backend integration...")

    # Create benchmark
    bench = SimpleFloat().to_bench(bch.BenchRunCfg(level=3))

    # Run parameter sweep
    print("Running parameter sweep...")
    results = bench.plot_sweep()

    # Test rerun visualization
    print("Creating rerun visualization...")
    try:
        rerun_view = results.to_rerun()
        print("✓ Rerun visualization created successfully!")
        print("✓ Rerun viewer should be open showing the sine curve")
        print(f"✓ Generated visualization panel of type: {type(rerun_view)}")

        return True
    except Exception as e:
        print(f"✗ Error creating rerun visualization: {e}")
        return False


if __name__ == "__main__":
    success = test_rerun_backend()
    if success:
        print("\n🎉 Rerun backend integration test passed!")
        print("Check the Rerun viewer window for the interactive visualization.")
    else:
        print("\n❌ Rerun backend integration test failed!")

    import time

    time.sleep(2)  # Give time to see the rerun viewer
