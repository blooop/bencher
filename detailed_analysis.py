#!/usr/bin/env python3
"""Detailed analysis of timeline animation issues."""

import sys
import os
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def detailed_analysis(png_path):
    """Analyze animation for labels, final frame position, and easing progression."""
    print(f"Analyzing animation: {png_path}")
    
    try:
        img = Image.open(png_path)
        frame_count = 0
        
        while True:
            try:
                width, height = img.size
                frame_rgb = img.convert('RGB')
                pixels = frame_rgb.load()
                
                # Find film strip area
                film_strip_y = None
                for y in range(height):
                    sample_x = width // 2
                    r, g, b = pixels[sample_x, y]
                    if r < 50 and g < 50 and b < 50:  # Dark film color
                        film_strip_y = y
                        break
                
                if film_strip_y:
                    # Find visible film frames
                    frames_found = []
                    in_frame = False
                    frame_start = None
                    
                    for x in range(width):
                        r, g, b = pixels[x, film_strip_y + 20]  # Inside frame area
                        is_light = r > 200 and g > 200 and b > 200  # Light frame background
                        
                        if is_light and not in_frame:
                            in_frame = True
                            frame_start = x
                        elif not is_light and in_frame:
                            in_frame = False
                            if frame_start is not None:
                                frames_found.append((frame_start, x))
                    
                    # Check for labels below the film strip
                    label_y = film_strip_y + 60  # Approximate label position
                    labels_found = []
                    
                    if label_y < height:
                        # Scan for text-like patterns (darker pixels that might be labels)
                        for x in range(0, width, 10):  # Sample every 10 pixels
                            if x < width:
                                r, g, b = pixels[x, label_y]
                                if r < 150 and g < 150 and b < 150:  # Darker pixels (text)\n                                    labels_found.append(x)\n                    \n                    # Check if this is likely the final frame by looking for background on right\n                    has_right_background = False\n                    if frames_found:\n                        rightmost_frame_end = max(end for _, end in frames_found)\n                        # Check if there's significant empty space to the right\n                        if rightmost_frame_end < width - 50:  # At least 50px of background\n                            has_right_background = True\n                    \n                    # Estimate which time steps are visible based on frame positions\n                    estimated_time_steps = []\n                    if len(frames_found) >= 3:\n                        # For a 5-step timeline, estimate which steps are visible\n                        frame_centers = [(start + end) // 2 for start, end in frames_found]\n                        if len(frame_centers) == 3:  # 3 visible frames\n                            # The middle frame should correspond to the center_frame\n                            # Rough estimation based on animation progression\n                            progress = frame_count / 9  # Approximate total frames\n                            center_step = int(progress * 4)  # 0 to 4 for 5 steps\n                            estimated_time_steps = [max(0, center_step-1), center_step, min(4, center_step+1)]\n                    \n                    print(f\"Frame {frame_count}: {len(frames_found)} visible frames, {len(labels_found)} label pixels\")\n                    if frames_found:\n                        print(f\"  Frame positions: {frames_found}\")\n                        print(f\"  Estimated time steps visible: {estimated_time_steps}\")\n                    \n                    if labels_found:\n                        print(f\"  Labels detected at x positions: {labels_found[:5]}...\")  # Show first 5\n                    else:\n                        print(f\"  ⚠️  NO LABELS DETECTED\")\n                    \n                    if has_right_background:\n                        print(f\"  ✓ Background visible on right side\")\n                    else:\n                        print(f\"  ✗ No background visible on right\")\n                    \n                    # Special analysis for what should be the final frame\n                    if frame_count >= 7:  # Later frames\n                        print(f\"  Final frame analysis:\")\n                        print(f\"    - Time step 4 (t=4) should be centered\")\n                        print(f\"    - Should see background on right\")\n                        print(f\"    - Should have label 't=4' below centered frame\")\n                \n                frame_count += 1\n                img.seek(frame_count)\n                \n            except EOFError:\n                break\n        \n        print(f\"\\nTotal frames: {frame_count}\")\n        print(f\"Animation duration: {frame_count / 10:.1f}s at 10fps\")\n        \n    except Exception as e:\n        print(f\"Error: {e}\")\n\nif __name__ == \"__main__\":\n    import glob\n    latest_files = sorted(glob.glob(\"cachedir/test_*/cartesian_*.png\"))\n    if latest_files:\n        detailed_analysis(latest_files[-1])\n    else:\n        print(\"No animation files found!\")