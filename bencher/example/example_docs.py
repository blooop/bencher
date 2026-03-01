import bencher as bch
from bencher.example.example_video import example_video
from bencher.example.example_image import example_image
from bencher.example.meta.example_meta_levels import example_meta_levels
from bencher.example.meta.example_meta_cat import example_meta_cat
from bencher.example.meta.example_meta_float import example_meta_float


if __name__ == "__main__":
    runner = bch.BenchRunner("example_docs")

    runner.add(example_image)
    runner.add(example_video)
    runner.add(example_meta_cat)
    runner.add(example_meta_float)
    runner.add(example_meta_levels)

    runner.run(level=2, grouped=True, show=True, cache_results=False)
