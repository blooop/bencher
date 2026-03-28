#!/usr/bin/env python3
"""Quick test for the timeline animation fix."""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bencher.results.manim_cartesian.cartesian_product_scene import render_animation
from bencher.bench_cfg import BenchCfg

# Simple test configuration with over_time dimension
class TestCfg:
    def __init__(self):
        self.all_vars = []
        # Add a simple spatial dimension
        self.all_vars.append(type('Var', (), {
            'name': 'test_dim', 
            'values': [1, 2, 3], 
            'meta': {}
        })())
        # Add an over_time dimension with 5 timesteps
        self.all_vars.append(type('Var', (), {
            'name': 'over_time', 
            'values': [0, 1, 2, 3, 4], 
            'meta': {}
        })())

if __name__ == "__main__":
    cfg = TestCfg()
    # Use timestamp to ensure unique filename and force regeneration
    timestamp = int(time.time())
    output_dir = f"cachedir/test_{timestamp}"
    output_path = render_animation(
        cfg, 
        width=400, 
        height=200, 
        fps=10,  # Lower fps for quicker generation
        output_dir=output_dir
    )
    print(f"Generated animation: {output_path}")