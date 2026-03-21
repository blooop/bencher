"""Tests for bencher.git_info module."""

import subprocess
import unittest
from unittest import mock

from bencher.git_info import git_time_event


class TestGitTimeEvent(unittest.TestCase):
    def test_returns_timestamp_and_hash(self):
        def fake(cmd, **_kwargs):
            if "rev-parse" in cmd:
                return b"abc1234def5678901234567890abcdef12345678\n"
            return b""

        with (
            mock.patch("subprocess.check_output", side_effect=fake),
            mock.patch("bencher.git_info.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2024-06-15 14:59"
            result = git_time_event()
        self.assertEqual(result, "2024-06-15 14:59 abc1234d")

    def test_returns_timestamp_outside_repo(self):
        with (
            mock.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "")),
            mock.patch("bencher.git_info.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2024-06-15 14:59"
            self.assertEqual(git_time_event(), "2024-06-15 14:59")

    def test_returns_timestamp_when_git_not_installed(self):
        with (
            mock.patch("subprocess.check_output", side_effect=FileNotFoundError),
            mock.patch("bencher.git_info.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2024-06-15 14:59"
            self.assertEqual(git_time_event(), "2024-06-15 14:59")

    def test_used_as_time_src(self):
        """git_time_event() works as time_src in plot_sweep."""
        import bencher as bn
        from bencher.example.benchmark_data import ExampleBenchCfg

        bench = bn.Bench("test_git", ExampleBenchCfg())
        run_cfg = bn.BenchRunCfg(over_time=True)
        res = bench.plot_sweep(
            input_vars=[ExampleBenchCfg.param.theta],
            run_cfg=run_cfg,
            time_src=bn.git_time_event(),
            plot_callbacks=False,
        )
        over_time_val = str(res.ds.coords["over_time"].values[0])
        self.assertRegex(over_time_val, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} [0-9a-f]{8}")


if __name__ == "__main__":
    unittest.main()
