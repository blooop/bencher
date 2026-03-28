#!/usr/bin/env python3
"""Test script to verify the new windowed over_time animation behavior."""

import bencher as bn
from bencher.results.manim_cartesian import CartesianProductCfg, SweepVar, render_animation

def test_windowed_animation():
    """Test the animation with more than 10 time steps to verify windowed behavior."""
    
    # Create a configuration with 15 time steps (should trigger windowed display)
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("spatial_dim", [0, 1, 2]),  # 3 values
            SweepVar("over_time", [f"t{i}" for i in range(15)]),  # 15 time steps
        ],
        result_names=["result"],
    )

    print("Rendering animation with 15 time steps...")
    print("Expected behavior: Should show windows of 10 frames, ending with frames t5-t14")
    
    animation_path = render_animation(
        cfg,
        width=640,
        height=400,
        fps=10,
        step_frames=3,
        output_dir="cachedir/test"
    )
    
    print(f"Animation saved to: {animation_path}")
    return animation_path

if __name__ == "__main__":
    test_windowed_animation()