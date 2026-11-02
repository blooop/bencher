"""The viewer for an ``.rrd`` matches the rerun release that wrote the file.

An ``.rrd`` starts with a 12-byte header: the magic ``RRF2``, then the writer's
version as ``[major, minor, patch, meta]`` bytes, then encoding options.  The viewer
reads that version, so a recording cached under one rerun release keeps its matching
viewer after the environment moves to another one — or drops ``rerun-sdk``.
"""

import tempfile
import unittest
from importlib.metadata import PackageNotFoundError, version as get_package_version
from pathlib import Path
from unittest import mock

from bencher.utils_rrd import _rrd_recorded_version, rrd_file_to_pane


def write_rrd_header(path: Path, version: bytes, magic: bytes = b"RRF2") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(magic + version + b"\x01\x02\x00\x00" + b"payload")
    return path


class TestRerunRrdHeaderVersion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_rerun_header_version_is_read_off_the_file(self):
        rrd = write_rrd_header(self.tmp / "a.rrd", bytes([0, 38, 2, 0]))
        assert _rrd_recorded_version(rrd) == "0.38.2"

    def test_rerun_header_without_a_release_version_gives_none(self):
        """A prerelease or dev build has no exact viewer name to ask the CDN for."""
        cases = {
            "prerelease": write_rrd_header(self.tmp / "b.rrd", bytes([0, 42, 0, 0x41])),
            "not an rrd": write_rrd_header(self.tmp / "c.rrd", bytes([0, 41, 0, 0]), b"PK\x03\x04"),
            "truncated": self.tmp / "d.rrd",
            "missing": self.tmp / "missing.rrd",
        }
        cases["truncated"].write_bytes(b"RRF2\x00")
        for name, path in cases.items():
            with self.subTest(case=name):
                assert _rrd_recorded_version(path) is None

    def test_rerun_viewer_for_an_old_recording_matches_its_writer(self):
        """A cached 0.38 recording opens in the 0.38 viewer, whatever is installed now."""
        rrd = write_rrd_header(self.tmp / "job" / "old.rrd", bytes([0, 38, 0, 0]))
        report = self.tmp / "report"
        installed_sdks = {
            "0.41 installed": mock.Mock(return_value="0.41.0"),
            "no rerun-sdk": mock.Mock(side_effect=PackageNotFoundError),
        }
        for name, get_version in installed_sdks.items():
            with self.subTest(installed=name):
                with mock.patch("bencher.utils_rrd.get_package_version", get_version):
                    pane = rrd_file_to_pane(rrd, report_dir=report)
                assert "_rrd/viewer_0.38.0.html" in pane.object
                assert (report / "_rrd" / "viewer_0.38.0.html").is_file()

    def test_rerun_explicit_viewer_version_wins_over_the_header(self):
        rrd = write_rrd_header(self.tmp / "job" / "old.rrd", bytes([0, 38, 0, 0]))
        pane = rrd_file_to_pane(rrd, viewer_version="0.40.1", report_dir=self.tmp / "report")
        assert "_rrd/viewer_0.40.1.html" in pane.object

    def test_rerun_unreadable_header_falls_back_to_the_installed_sdk(self):
        rrd = write_rrd_header(self.tmp / "job" / "x.rrd", bytes([0, 42, 0, 0x41]))
        with mock.patch("bencher.utils_rrd.get_package_version", return_value="0.41.0"):
            pane = rrd_file_to_pane(rrd, report_dir=self.tmp / "report")
        assert "_rrd/viewer_0.41.0.html" in pane.object

    def test_rerun_sdk_writes_the_header_the_reader_expects(self):
        """A real recording from the installed SDK names that SDK's version."""
        try:
            import rerun as rr

            installed = get_package_version("rerun-sdk")
        except (ImportError, PackageNotFoundError):  # pragma: no cover
            self.skipTest("rerun-sdk is not installed")
        rrd = self.tmp / "real.rrd"
        rec = rr.RecordingStream("bencher_header_test")
        rec.save(str(rrd))
        rec.log("p", rr.Points3D([[1.0, 2.0, 3.0]]))
        rec.flush()
        rec.disconnect()
        assert _rrd_recorded_version(rrd) == installed


if __name__ == "__main__":
    unittest.main()
