#!/usr/bin/env python3
"""Test to verify the smooth transition from static frame to over_time animation."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bencher.results.manim_cartesian.cartesian_product_scene import render_animation


class TestCfg:
    def __init__(self):
        self.all_vars = []
        # Add spatial dimensions for more complexity
        self.all_vars.append(type("Var", (), {"name": "x", "values": [1, 2], "meta": {}})())
        self.all_vars.append(type("Var", (), {"name": "y", "values": [1, 2, 3], "meta": {}})())
        # Over time dimension to test the transition fix
        self.all_vars.append(
            type(
                "Var",
                (),
                {
                    "name": "over_time",
                    "values": [
                        f"t{i}" for i in range(12)
                    ],  # 12 time steps to trigger windowed animation
                    "meta": {},
                },
            )()
        )


def test_smooth_transition():
    """Test that the transition from spatial to over_time dimensions is smooth."""
    print("Testing smooth transition fix...")
    print("- Should show spatial dimensions first (2x3 grid)")
    print("- Then transition to over_time without jarring slide-in")
    print("- Film strip should appear with last frame positioned where static frame was")
    print("- Then show time progression smoothly")

    cfg = TestCfg()
    timestamp = int(time.time())
    output_dir = f"cachedir/test_transition_{timestamp}"

    output_path = render_animation(
        cfg,
        width=500,
        height=300,
        fps=10,
        output_dir=output_dir,
    )

    print(f"Generated: {output_path}")
    print("Check the animation to verify:")
    print("1. No jarring horizontal slide-in when transitioning to over_time")
    print("2. Film strip appears smoothly at the correct position")
    print("3. Time progression is shown through frame windowing, not horizontal sliding")

    return output_path


if __name__ == "__main__":
    test_smooth_transition()
