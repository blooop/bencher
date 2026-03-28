#!/usr/bin/env python3
"""Test to verify the last frame centering logic works correctly."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bencher.results.manim_cartesian.cartesian_product_scene import render_animation


def test_centering(time_steps, test_name):
    """Test centering with a specific number of time steps."""

    class TestCfg:
        def __init__(self):
            self.all_vars = []
            # Simple spatial dimension
            self.all_vars.append(type("Var", (), {"name": "x", "values": [1, 2], "meta": {}})())
            # Variable number of time steps
            self.all_vars.append(
                type(
                    "Var", (), {"name": "over_time", "values": list(range(time_steps)), "meta": {}}
                )()
            )

    cfg = TestCfg()
    timestamp = int(time.time())
    output_dir = f"cachedir/test_centering_{timestamp}"

    print(f"\n=== Testing {test_name}: {time_steps} time steps ===")
    print("Expected behavior: Last frame should be centered in the visible window")
    print("Max visible frames = 3, so for centering:")

    if time_steps <= 3:
        print("All frames should fit, no scrolling needed")
    else:
        center_pos = max(0, time_steps - 1 - 3 // 2)  # 3 // 2 = 1
        expected_center = time_steps - 1 - 1  # Last frame - 1 for centering
        print(f"Last frame (index {time_steps - 1}) should be centered")
        print(f"Expected start position for centering: {center_pos}")
        print(
            f"This means visible frames should be: [{center_pos}, {center_pos + 1}, {center_pos + 2}]"
        )
        print(
            f"So last frame (index {time_steps - 1}) is in position: {(time_steps - 1) - center_pos}"
        )

    output_path = render_animation(cfg, width=600, height=300, fps=8, output_dir=output_dir)
    print(f"Generated: {output_path}")
    return output_path


if __name__ == "__main__":
    # Test different scenarios
    test_centering(3, "Small case")  # Should fit all frames
    test_centering(5, "Medium case")  # Should center last frame
    test_centering(8, "Large case")  # Should center last frame

    print("\n=== Test Summary ===")
    print("Check the generated animations to verify:")
    print("1. Final animation frame shows the last time step centered")
    print("2. Animation smoothly scrolls to center the last frame")
    print("3. No frames skip past the center position")
