#!/usr/bin/env python3
"""Test script to verify normal behavior with ≤10 frames."""

from bencher.results.manim_cartesian import CartesianProductCfg, SweepVar, render_animation


def test_normal_animation():
    """Test the animation with 8 time steps (should use normal slide-in behavior)."""

    # Create a configuration with 8 time steps (should NOT trigger windowed display)
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("spatial_dim", [0, 1, 2]),  # 3 values
            SweepVar("over_time", [f"t{i}" for i in range(8)]),  # 8 time steps
        ],
        result_names=["result"],
    )

    print("Rendering animation with 8 time steps...")
    print("Expected behavior: Should use normal slide-in animation (not windowed)")

    animation_path = render_animation(
        cfg, width=640, height=400, fps=10, step_frames=3, output_dir="cachedir/test"
    )

    print(f"Animation saved to: {animation_path}")
    return animation_path


if __name__ == "__main__":
    test_normal_animation()
