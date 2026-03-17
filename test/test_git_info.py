"""Tests for bencher.git_info module."""

import subprocess
import unittest
from unittest import mock

from bencher.git_info import git_time_event


class TestGitTimeEvent(unittest.TestCase):
    def test_returns_date_and_hash_in_repo(self):
        result = git_time_event()
        # We're in a git repo, so should get "YYYY-MM-DD abcdefgh"
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} [0-9a-f]{8}")

    def test_returns_empty_outside_repo(self):
        with mock.patch(
            "subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "")
        ):
            self.assertEqual(git_time_event(), "")

    def test_returns_empty_when_git_not_installed(self):
        with mock.patch("subprocess.check_output", side_effect=FileNotFoundError):
            self.assertEqual(git_time_event(), "")

    def test_falls_back_to_hash_without_date(self):
        def fake(cmd, cwd=None, stderr=None):
            if "rev-parse" in cmd:
                return b"a" * 40 + b"\n"
            if "log" in cmd:
                return b""
            return b""

        with mock.patch("subprocess.check_output", side_effect=fake):
            self.assertEqual(git_time_event(), "a" * 8)

    def test_used_as_time_event(self):
        """git_time_event() works as a time_event in a real sweep."""
        import bencher as bch
        from bencher.example.benchmark_data import ExampleBenchCfg

        bench = bch.Bench("test_git", ExampleBenchCfg())
        run_cfg = bch.BenchRunCfg(over_time=True, time_event=bch.git_time_event())
        res = bench.plot_sweep(
            input_vars=[ExampleBenchCfg.param.theta],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )
        ot = str(res.ds.coords["over_time"].values[0])
        self.assertRegex(ot, r"\d{4}-\d{2}-\d{2} [0-9a-f]{8}")


if __name__ == "__main__":
    unittest.main()
