"""Generate thumbnail screenshots from pre-committed HTML reports.

This lightweight script is designed for ReadTheDocs builds. It walks the
committed HTML reports and creates PNG thumbnails using Playwright, without
re-running any examples.
"""

from __future__ import annotations

import io
from pathlib import Path

REPORTS_EXTRA_DIR = Path("docs/_extra/reference/meta")
THUMBS_EXTRA_DIR = REPORTS_EXTRA_DIR / "_thumbs"


def _resize_and_save_png(png_data: bytes, thumb_path: Path, thumb_width: int = 480) -> None:
    """Resize screenshot PNG data to thumbnail width and save to disk."""
    from PIL import Image

    img = Image.open(io.BytesIO(png_data))
    ratio = thumb_width / img.width
    img = img.resize((thumb_width, int(img.height * ratio)), Image.Resampling.LANCZOS)
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(thumb_path)


def generate_thumbnails() -> None:
    """Walk committed HTML reports and generate thumbnail PNGs."""
    from playwright.sync_api import sync_playwright

    report_dirs = sorted(REPORTS_EXTRA_DIR.rglob("_reports"))
    html_files = []
    for report_dir in report_dirs:
        html_files.extend(sorted(report_dir.rglob("*.html")))

    if not html_files:
        print("No HTML reports found — nothing to thumbnail.")
        return

    print(f"Generating thumbnails for {len(html_files)} HTML reports...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 900})

        for html_path in html_files:
            # Derive thumbnail path: _reports/<section>/<stem>/<name>.html
            # → _thumbs/<section>/<stem>.png
            # The report dir structure is: _reports/<example_stem>/<bench_name>.html
            # within a section subdirectory of REPORTS_EXTRA_DIR
            reports_parent = html_path.parent.parent  # up from _reports/<stem>/
            section_rel = reports_parent.relative_to(REPORTS_EXTRA_DIR)
            example_stem = html_path.parent.name
            thumb_path = THUMBS_EXTRA_DIR / section_rel / f"{example_stem}.png"

            try:
                page.set_viewport_size({"width": 1200, "height": 900})
                page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=15000)
                page.wait_for_timeout(2000)
                png_data = page.screenshot()
                _resize_and_save_png(png_data, thumb_path)
                print(f"  {thumb_path}")
            except Exception as e:  # noqa: BLE001
                print(f"  WARNING: Failed to thumbnail {html_path.name}: {e}")

        browser.close()

    print("Done generating thumbnails.")


if __name__ == "__main__":
    generate_thumbnails()
