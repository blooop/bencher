#!/usr/bin/env python3
"""Test to verify timeline labels (t=0, t=1, etc.) are showing correctly."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bencher.results.manim_cartesian.cartesian_product_scene import render_animation


def test_timeline_labels():
    """Test that timeline labels are rendered correctly."""

    class TestCfg:
        def __init__(self):
            self.all_vars = []
            # Simple spatial dimension
            self.all_vars.append(type("Var", (), {"name": "x", "values": [1, 2], "meta": {}})())
            # Over time dimension with several steps to test labels
            self.all_vars.append(
                type(
                    "Var",
                    (),
                    {
                        "name": "over_time",
                        "values": [f"step_{i}" for i in range(8)],  # 8 time steps
                        "meta": {},
                    },
                )()
            )

    cfg = TestCfg()
    timestamp = int(time.time())
    output_dir = f"cachedir/test_labels_{timestamp}"

    print("Testing timeline with 8 time steps...")
    print("Expected behavior:")
    print("- Should show only 2-3 frames at a time (windowed view)")
    print("- Timeline numbers (t=0, t=1, t=2, etc.) should appear below frames")
    print("- Animation should slide from right, stop when last frame (t=7) is centered")
    print("- Animation should be max 2 seconds")

    output_path = render_animation(
        cfg,
        width=600,
        height=300,
        fps=10,  # 10 fps so we can count frames
        output_dir=output_dir,
    )

    print(f"Generated: {output_path}")
    print("Check the animation to verify:")
    print("1. Timeline labels (t=0, t=1, etc.) are visible below frames")
    print("2. Only 2-3 frames visible at once")
    print("3. Smooth sliding animation from right")
    print("4. Last frame (t=7) ends up centered")

    return output_path


if __name__ == "__main__":
    test_timeline_labels()
