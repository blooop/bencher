#!/usr/bin/env python3
"""Analyze animation frames to verify the timeline centering fix."""

import sys
import os
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def analyze_animation(png_path):
    """Analyze the animation frames to check if centering is working."""
    print(f"Analyzing animation: {png_path}")

    try:
        img = Image.open(png_path)
        frame_count = 0

        # Extract some key information about frames
        while True:
            try:
                # Analyze this frame
                width, height = img.size

                # Convert to RGB for analysis
                frame_rgb = img.convert("RGB")
                pixels = frame_rgb.load()

                # Look for film strip characteristics
                # Find the darkest horizontal band (should be the film strip)
                film_strip_y = None
                for y in range(height):
                    # Check if this row has the dark film color
                    sample_x = width // 2
                    r, g, b = pixels[sample_x, y]
                    if r < 50 and g < 50 and b < 50:  # Dark film color
                        film_strip_y = y
                        break

                if film_strip_y:
                    # Analyze the film frames on this row
                    frames_found = []
                    in_frame = False
                    frame_start = None

                    for x in range(width):
                        r, g, b = pixels[x, film_strip_y + 20]  # Inside frame area
                        is_light = r > 200 and g > 200 and b > 200  # Light frame background

                        if is_light and not in_frame:
                            # Found start of frame
                            in_frame = True
                            frame_start = x
                        elif not is_light and in_frame:
                            # Found end of frame
                            in_frame = False
                            if frame_start is not None:
                                frames_found.append((frame_start, x))

                    print(
                        f"  Frame {frame_count}: {len(frames_found)} visible film frames at y={film_strip_y}"
                    )
                    if frames_found:
                        # Describe the frame positions
                        frame_positions = [f"({start}-{end})" for start, end in frames_found]
                        print(f"    Frame positions: {', '.join(frame_positions)}")

                        # Check if frames are centered
                        total_frame_width = frames_found[-1][1] - frames_found[0][0]
                        center_pos = (frames_found[0][0] + frames_found[-1][1]) / 2
                        screen_center = width / 2
                        offset_from_center = abs(center_pos - screen_center)

                        print(
                            f"    Frame group center: {center_pos:.1f}, Screen center: {screen_center}"
                        )
                        print(f"    Offset from center: {offset_from_center:.1f} pixels")

                        if offset_from_center < 10:
                            print(f"    ✓ Frames are well centered")
                        else:
                            print(f"    ✗ Frames are off-center by {offset_from_center:.1f}px")

                frame_count += 1
                img.seek(frame_count)

            except EOFError:
                break

        print(f"Total frames analyzed: {frame_count}")

        # Analyze the last few frames specifically
        print(f"\nAnalyzing last frame (frame {frame_count - 1}) for centering issues...")
        img.seek(frame_count - 1)
        # Re-run the analysis for the last frame with more detail

    except Exception as e:
        print(f"Error analyzing animation: {e}")


if __name__ == "__main__":
    # Use the latest generated animation file
    import glob

    latest_files = sorted(glob.glob("cachedir/test_*/cartesian_*.png"))
    if latest_files:
        analyze_animation(latest_files[-1])
    else:
        print("No animation files found!")
