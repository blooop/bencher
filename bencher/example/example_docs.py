import bencher as bn
from bencher.example.example_video import example_video
from bencher.example.example_image import example_image


if __name__ == "__main__":
    runner = bn.BenchRunner("example_docs")

    runner.add(example_image)
    runner.add(example_video)

    runner.run(level=2, grouped=True, show=True, cache_results=False)
