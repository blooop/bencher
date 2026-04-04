"""Sweep num_tabs to see how the tab bar wraps with fixed styling (marker 4, gap 4, pad 10)."""

import bencher as bn
from PIL import Image, ImageDraw, ImageFont


VIEWPORT_W = 1200
BAR_MAX_H = 600
MARKER_SIZE = 4
GAP = 4
PAD = 10
BORDER_R = 4


class TabBarSweep(bn.ParametrizedSweep):
    num_tabs = bn.IntSweep(default=10, bounds=(1, 100), doc="Number of tabs in the bar")

    tab_bar_image = bn.ResultImage()
    rows_used = bn.ResultFloat(units="rows", doc="How many rows the tabs wrap into")
    overflow = bn.ResultFloat(units="bool", doc="1 if tabs exceed max bar height, else 0")

    def benchmark(self):
        btn_pad_x = MARKER_SIZE
        btn_pad_y = int(MARKER_SIZE * 0.7)
        char_w = MARKER_SIZE * 0.6

        # Build button sizes
        btn_sizes = []
        for i in range(self.num_tabs):
            label = f"Tab {i + 1}"
            w = int(len(label) * char_w) + 2 * btn_pad_x
            h = MARKER_SIZE + 2 * btn_pad_y
            btn_sizes.append((w, h, label))

        # Flow-wrap buttons into rows
        rows = []
        row = []
        row_w = 0
        avail_w = VIEWPORT_W - 2 * PAD
        for w, h, label in btn_sizes:
            needed = w + (GAP if row else 0)
            if row and row_w + needed > avail_w:
                rows.append(row)
                row = []
                row_w = 0
            row_w += w + (GAP if row else 0)
            row.append((w, h, label))
        if row:
            rows.append(row)

        self.rows_used = len(rows)
        btn_h = btn_sizes[0][1] if btn_sizes else MARKER_SIZE
        bar_h = 2 * PAD + len(rows) * btn_h + max(0, len(rows) - 1) * GAP
        self.overflow = 1 if bar_h > BAR_MAX_H else 0
        img_h = min(bar_h, BAR_MAX_H)

        # Draw
        img = Image.new("RGB", (VIEWPORT_W, img_h), (23, 23, 23))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", MARKER_SIZE
            )
        except OSError:
            font = ImageFont.load_default()

        y = PAD
        for ri, row_btns in enumerate(rows):
            if y + btn_h > img_h:
                break
            x = PAD
            for w, h, label in row_btns:
                is_last = ri == len(rows) - 1 and label == row_btns[-1][2]
                if is_last:
                    fill = (230, 230, 230)
                    text_fill = (0, 0, 0)
                else:
                    fill = (60, 60, 60)
                    text_fill = (255, 255, 255)

                draw.rounded_rectangle([x, y, x + w, y + h], radius=BORDER_R, fill=fill)
                draw.text((x + btn_pad_x, y + btn_pad_y), label, fill=text_fill, font=font)
                x += w + GAP
            y += btn_h + GAP

        filepath = bn.gen_image_path("tab_bar")
        img.save(filepath, "PNG")
        self.tab_bar_image = str(filepath)


def example_tab_bar_sweep(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = bn.Bench("tab_bar_sweep", TabBarSweep(), run_cfg=run_cfg)
    bench.result_vars = ["tab_bar_image", "rows_used", "overflow"]

    bench.add_plot_callback(bn.BenchResult.to_sweep_summary)
    bench.add_plot_callback(bn.BenchResult.to_panes, level=2)

    bench.plot_sweep(
        "Tab Bar: num_tabs sweep",
        input_vars=["num_tabs"],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_tab_bar_sweep)
