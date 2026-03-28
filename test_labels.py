#!/usr/bin/env python3
"""Simple timeline test to isolate label issues."""

import sys
import os
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bencher.results.manim_cartesian.cartesian_product_scene import TimelineShape, Shape


def test_timeline_labels():
    """Test timeline label generation and rendering directly."""
    # Create a simple timeline
    inner_shape = Shape()
    timeline = TimelineShape(inner_shape, count=3, center_frame=1, max_visible_frames=3)

    # Create a test image
    width, height = 400, 200
    img = Image.new("RGB", (width, height), (255, 255, 255))  # White background
    draw = ImageDraw.Draw(img)

    # Draw the timeline at the center
    timeline.draw(draw, 50, 50)

    # Check if labels were generated
    print(f"Generated {len(timeline._label_info)} labels:")
    for i, label in enumerate(timeline._label_info):
        print(f"  {i + 1}. '{label['text']}' at ({label['x']}, {label['y']})")

    # Save the test image
    img.save("cachedir/timeline_label_test.png")
    print("Saved test image to cachedir/timeline_label_test.png")

    # Also draw labels with large red text to see if they appear
    from bencher.results.manim_cartesian.cartesian_product_scene import _get_font

    font = _get_font(24)  # Large font for visibility

    for label in timeline._label_info:
        x = label["x"] + 50  # Add timeline x offset
        y = label["y"] + 50  # Add timeline y offset
        draw.text((x, y), label["text"], fill=(255, 0, 0), font=font)  # Red text

    img.save("cachedir/timeline_label_test_annotated.png")
    print("Saved annotated test image to cachedir/timeline_label_test_annotated.png")


if __name__ == "__main__":
    os.makedirs("cachedir", exist_ok=True)
    test_timeline_labels()
