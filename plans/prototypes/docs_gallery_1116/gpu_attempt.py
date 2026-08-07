"""One-off: try to get genuinely GPU-backed headless Chrome for the screenshot bench."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from screenshot_bench import PROTO_DIR, bench_config  # noqa: E402

r = bench_config(
    "gpu_attempt_vulkan",
    {
        "executable_path": "/usr/bin/google-chrome",
        "args": [
            "--use-angle=vulkan",
            "--enable-features=Vulkan,DefaultANGLEVulkan,VulkanFromANGLE",
            "--enable-gpu",
            "--ignore-gpu-blocklist",
        ],
    },
    PROTO_DIR / "out" / "screenshot_gpu_vulkan.png",
)
print(json.dumps(r))
out = PROTO_DIR / "out" / "measurements_screenshot.json"
data = json.loads(out.read_text())
data.append(r)
out.write_text(json.dumps(data, indent=2))
