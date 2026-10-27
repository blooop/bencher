"""Tests for downloading the rerun web-viewer npm package."""

import base64
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from bencher import rerun_web_viewer


def _tarball(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _integrity(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


class TestDownloadWebViewer(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))

    def _serve(self, tarball: bytes, integrity: str | None = None):
        meta = {
            "dist": {
                "tarball": "https://registry.npmjs.org/x.tgz",
                "integrity": integrity or _integrity(tarball),
            }
        }

        def fetch(url, _timeout):
            return json.dumps(meta).encode() if url.endswith("/0.40.0") else tarball

        return mock.patch.object(rerun_web_viewer, "_fetch", side_effect=fetch)

    def test_writes_package_files_under_versioned_dir(self):
        tgz = _tarball(
            {
                "package/index.js": b'x = await import("./re_viewer");',
                "package/re_viewer.js": b"glue",
                "package/re_viewer_bg.wasm": b"\0asm",
                "package/package.json": b"{}",
            }
        )
        with self._serve(tgz):
            out = rerun_web_viewer.download_web_viewer("0.40.0", self.tmp)
        assert out == self.tmp / "web-viewer@0.40.0"
        assert (out / "re_viewer_bg.wasm").read_bytes() == b"\0asm"
        assert (out / "package.json").is_file()
        # A plain file server cannot resolve the extensionless import.
        assert (out / "index.js").read_text() == 'x = await import("./re_viewer.js");'
        # No temporary directory is left next to it.
        assert [p.name for p in self.tmp.iterdir()] == ["web-viewer@0.40.0"]

    def test_existing_copy_is_not_fetched_again(self):
        out = self.tmp / "web-viewer@0.40.0"
        out.mkdir()
        for name in rerun_web_viewer.REQUIRED_FILES:
            (out / name).write_text("x")
        with mock.patch.object(rerun_web_viewer, "_fetch") as fetch:
            rerun_web_viewer.download_web_viewer("0.40.0", self.tmp)
        fetch.assert_not_called()

    def test_bad_integrity_writes_nothing(self):
        tgz = _tarball({"package/index.js": b"js"})
        with (
            self._serve(tgz, integrity=_integrity(b"other")),
            pytest.raises(ValueError, match="sha512"),
        ):
            rerun_web_viewer.download_web_viewer("0.40.0", self.tmp)
        assert not any(self.tmp.iterdir())

    def test_missing_wasm_writes_nothing(self):
        tgz = _tarball({"package/index.js": b"js", "package/re_viewer.js": b"glue"})
        with self._serve(tgz), pytest.raises(ValueError, match="missing"):
            rerun_web_viewer.download_web_viewer("0.40.0", self.tmp)
        assert not any(self.tmp.iterdir())

    def test_unknown_glue_import_writes_nothing(self):
        """A release that loads its glue some other way must not be served half-fixed."""
        tgz = _tarball(
            {
                "package/index.js": b'import init from "./other_glue.js";',
                "package/re_viewer.js": b"glue",
                "package/re_viewer_bg.wasm": b"\0asm",
            }
        )
        with self._serve(tgz), pytest.raises(ValueError, match="re_viewer exactly once"):
            rerun_web_viewer.download_web_viewer("0.40.0", self.tmp)
        assert not any(self.tmp.iterdir())

    def test_path_traversal_is_refused(self):
        tgz = _tarball({"package/../../evil.js": b"x"})
        with self._serve(tgz), pytest.raises(ValueError, match="Unsafe path"):
            rerun_web_viewer.download_web_viewer("0.40.0", self.tmp)
        assert not (self.tmp.parent / "evil.js").exists()
