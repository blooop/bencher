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
                    labels_found = []

                    if label_y < height:
                        # Scan for text-like patterns (darker pixels that might be labels)
                        for x in range(0, width, 10):  # Sample every 10 pixels
                            if x < width:
                                r, g, b = pixels[x, label_y]
                                if r < 150 and g < 150 and b < 150:  # Darker pixels (text)
                                    labels_found.append(x)

                    # Check if this is likely the final frame by looking for background on right
                    has_right_background = False
                    if frames_found:
                        rightmost_frame_end = max(end for _, end in frames_found)
                        # Check if there's significant empty space to the right
                        if rightmost_frame_end < width - 50:  # At least 50px of background
                            has_right_background = True

                    # Estimate which time steps are visible based on frame positions
                    estimated_time_steps = []
                    if len(frames_found) >= 3:
                        # For a 5-step timeline, estimate which steps are visible
                        frame_centers = [(start + end) // 2 for start, end in frames_found]
                        if len(frame_centers) == 3:  # 3 visible frames
                            # The middle frame should correspond to the center_frame
                            # Rough estimation based on animation progression
                            progress = frame_count / 9  # Approximate total frames
                            center_step = int(progress * 4)  # 0 to 4 for 5 steps
                            estimated_time_steps = [
                                max(0, center_step - 1),
                                center_step,
                                min(4, center_step + 1),
                            ]

                    print(
                        f"Frame {frame_count}: {len(frames_found)} visible frames, {len(labels_found)} label pixels"
                    )
                    if frames_found:
                        print(f"  Frame positions: {frames_found}")
                        print(f"  Estimated time steps visible: {estimated_time_steps}")

                    if labels_found:
                        print(
                            f"  Labels detected at x positions: {labels_found[:5]}..."
                        )  # Show first 5
                    else:
                        print("  ⚠️  NO LABELS DETECTED")

                    if has_right_background:
                        print("  ✓ Background visible on right side")
                    else:
                        print("  ✗ No background visible on right")

                    # Special analysis for what should be the final frame
                    if frame_count >= 7:  # Later frames
                        print("  Final frame analysis:")
                        print("    - Time step 4 (t=4) should be centered")
                        print("    - Should see background on right")
                        print("    - Should have label 't=4' below centered frame")

                frame_count += 1
                img.seek(frame_count)

            except EOFError:
                break

        print(f"\nTotal frames: {frame_count}")
        print(f"Animation duration: {frame_count / 10:.1f}s at 10fps")

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: {e}")


if __name__ == "__main__":
    import glob

    latest_files = sorted(glob.glob("cachedir/test_*/cartesian_*.png"))
    if latest_files:
        detailed_analysis(latest_files[-1])
    else:
        print("No animation files found!")
