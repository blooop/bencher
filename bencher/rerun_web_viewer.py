"""Download the ``@rerun-io/web-viewer`` npm package to host it yourself.

Reports load the rerun web viewer from unpkg by default. To serve it from your own
server instead, copy the package there once per rerun version and point
``BENCHER_RERUN_VIEWER_URL`` at it::

    python -m bencher.rerun_web_viewer 0.40.0 /srv/reports/_rerun
    export BENCHER_RERUN_VIEWER_URL='/_rerun/web-viewer@{version}/'

The package comes from the npm registry, which has no file-size limit, and its
sha512 is checked against the registry's ``dist.integrity`` before anything is
written. The server must send ``.wasm`` files as ``application/wasm``.

``index.js`` imports ``"./re_viewer"`` with no extension. unpkg resolves that to
``re_viewer.js``, but a plain file server does not, so this module rewrites that
one import to ``"./re_viewer.js"``. Nothing else in the package is changed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REGISTRY_URL = "https://registry.npmjs.org/@rerun-io/web-viewer/{version}"

# The files the viewer page loads: index.js imports re_viewer.js next to itself,
# and fetches re_viewer_bg.wasm from the same directory.
REQUIRED_FILES = ("index.js", "re_viewer.js", "re_viewer_bg.wasm")

_GLUE_IMPORT_RE = re.compile(r"""import\(\s*(["'])\./re_viewer(\.js)?\1\s*\)""")


def _fetch(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (https only)
        return resp.read()


def _check_integrity(data: bytes, integrity: str) -> None:
    algo, _, expected = integrity.partition("-")
    if algo != "sha512":
        raise ValueError(f"Unsupported npm integrity algorithm {algo!r}")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
    if actual != expected:
        raise ValueError("Tarball sha512 does not match the npm registry's dist.integrity")


def _unpack(data: bytes, out_dir: Path, version: str) -> None:
    """Write the plain files under ``package/`` in the npm tarball *data* to *out_dir*."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            rel = Path(member.name)
            if not member.isfile() or rel.parts[:1] != ("package",):
                continue
            if ".." in rel.parts or rel.is_absolute():
                raise ValueError(f"Unsafe path in tarball: {member.name!r}")
            out = out_dir.joinpath(*rel.parts[1:])
            out.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            if src is None:  # not reached: member.isfile()
                continue
            with src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    missing = [name for name in REQUIRED_FILES if not (out_dir / name).is_file()]
    if missing:
        raise ValueError(f"web-viewer@{version} tarball is missing {missing}")
    _fix_glue_import(out_dir / "index.js", version)
    out_dir.chmod(0o755)


def _fix_glue_import(index_js: Path, version: str) -> None:
    """Make ``index.js`` import ``./re_viewer.js``, a path a plain file server can serve."""
    text = index_js.read_text(encoding="utf-8")
    if len(_GLUE_IMPORT_RE.findall(text)) != 1:
        raise ValueError(
            f"web-viewer@{version} index.js does not import ./re_viewer exactly once;"
            " this module needs updating for that release"
        )
    index_js.write_text(
        _GLUE_IMPORT_RE.sub(lambda m: f"import({m[1]}./re_viewer.js{m[1]})", text),
        encoding="utf-8",
    )


def download_web_viewer(version: str, dest_root: str | Path, timeout: float = 600) -> Path:
    """Write the web-viewer package for *version* to ``dest_root/web-viewer@<version>/``.

    Returns that directory. An existing directory with all of ``REQUIRED_FILES`` is
    left as it is. The package is unpacked to a temporary directory next to it and
    renamed into place, so a reader never sees a half-written copy.
    """
    dest = Path(dest_root) / f"web-viewer@{version}"
    if all((dest / name).is_file() for name in REQUIRED_FILES):
        return dest

    meta = json.loads(_fetch(REGISTRY_URL.format(version=version), timeout))
    tarball_url = meta["dist"]["tarball"]
    if not tarball_url.startswith("https://"):
        raise ValueError(f"Refusing non-https tarball URL {tarball_url!r}")
    data = _fetch(tarball_url, timeout)
    _check_integrity(data, meta["dist"]["integrity"])

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{dest.name}.", dir=dest.parent))
    try:
        _unpack(data, tmp, version)
        if dest.exists():
            shutil.rmtree(dest)
        tmp.rename(dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("version", help="rerun version, e.g. 0.40.0")
    parser.add_argument("dest_root", help="directory that gets web-viewer@<version>/")
    args = parser.parse_args(argv)
    sys.stdout.write(f"{download_web_viewer(args.version, args.dest_root)}\n")


if __name__ == "__main__":
    main()
