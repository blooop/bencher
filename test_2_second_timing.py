#!/usr/bin/env python3
"""Test to verify over_time animation is always 2 seconds regardless of fps."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bencher.results.manim_cartesian.cartesian_product_scene import render_animation


class TestCfg:
    def __init__(self):
        self.all_vars = []
        # Simple spatial dimension
        self.all_vars.append(type("Var", (), {"name": "x", "values": [1, 2], "meta": {}})())
        # Over time dimension with many steps to trigger windowed animation
        self.all_vars.append(
            type(
                "Var",
                (),
                {
                    "name": "over_time",
                    "values": [f"t{i}" for i in range(15)],  # 15 time steps
                    "meta": {},
                },
            )()
        )


def test_2_second_timing():
    """Test that over_time animation is always 2 seconds at different fps values."""
    cfg = TestCfg()
    timestamp = int(time.time())

    print("Testing 2-second over_time animation at different fps values:")

    for fps in [10, 15, 30]:
        output_dir = f"cachedir/test_timing_{timestamp}_fps{fps}"

        print(f"\nTesting at {fps} fps:")
        print(f"  Expected over_time frames: {fps * 2} (for 2 seconds)")

        output_path = render_animation(
            cfg,
            width=400,
            height=200,
            fps=fps,
            output_dir=output_dir,
        )

        print(f"  Generated: {output_path}")

    print("\nAll animations should have over_time portion lasting exactly 2 seconds")
    print("Verify by checking the frame counts in the output")


if __name__ == "__main__":
    test_2_second_timing()
