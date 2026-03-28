#!/usr/bin/env python3
"""Detailed analysis of timeline animation issues."""

import sys
import os
from PIL import Image

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
                frame_rgb = img.convert("RGB")
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
                    labels_found = 0

                    if label_y < height:
                        # Scan for text-like patterns
                        for x in range(0, width, 5):
                            if x < width:
                                r, g, b = pixels[x, label_y]
                                if r < 150 and g < 150 and b < 150:  # Darker text pixels
                                    labels_found += 1

                    # Check for background on right side
                    has_right_background = False
                    if frames_found:
                        rightmost_frame_end = max(end for _, end in frames_found)
                        if rightmost_frame_end < width - 50:  # At least 50px background
                            has_right_background = True

                    print(
                        f"Frame {frame_count}: {len(frames_found)} frames, {labels_found} label pixels"
                    )
                    if frames_found:
                        print(f"  Frames: {frames_found}")

                    if labels_found > 20:  # Threshold for detecting actual text
                        print(f"  ✓ Labels detected")
                    else:
                        print(f"  ✗ NO LABELS - only {labels_found} text pixels")

                    if has_right_background:
                        print(f"  ✓ Background visible on right")
                    else:
                        print(f"  ✗ No right background visible")

                frame_count += 1
                img.seek(frame_count)

            except EOFError:
                break

        print(f"\\nTotal frames: {frame_count}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Test with a specific file
    test_file = (
        "cachedir/cartesian/cartesian_dim_1_3_dim_2_3_dim_3_2_dim_4_2_over_time_5_320x200.png"
    )
    if os.path.exists(test_file):
        detailed_analysis(test_file)
    else:
        print(f"File not found: {test_file}")
        import glob

        latest_files = sorted(glob.glob("cachedir/test_*/cartesian_*.png"))
        if latest_files:
            detailed_analysis(latest_files[-1])
        else:
            print("No animation files found!")
