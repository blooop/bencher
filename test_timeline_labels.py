#!/usr/bin/env python3
"""Test script to verify timeline labels are now rendered at full screen size."""

from bencher.results.manim_cartesian import CartesianProductCfg, SweepVar, render_animation

def test_timeline_label_size():
    """Test that timeline labels maintain full screen size even when shape is scaled."""
    
    # Create a configuration that will likely require scaling
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("dim1", [0, 1, 2]),  
            SweepVar("dim2", [0, 1, 2]),  
            SweepVar("dim3", [0, 1]),  
            SweepVar("over_time", [f"t{i}" for i in range(8)]),  # 8 time steps
        ],
        result_names=["result"],
    )

    print("Rendering animation with 8 time steps and complex spatial dimensions...")
    print("Timeline labels should now be rendered at full screen size (24pt)")
    
    animation_path = render_animation(
        cfg,
        width=400,  # Smaller width to force scaling
        height=300,
        fps=10,
        step_frames=3,
        output_dir="cachedir/test"
    )
    
    print(f"Animation saved to: {animation_path}")
    return animation_path

if __name__ == "__main__":
    test_timeline_label_size()