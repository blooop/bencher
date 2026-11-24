"""The source hash rule and the ``bencher stamp`` command."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from bencher.render import main as bencher_main
from bencher.source_link import (
    REPORT_ROOT_ENV,
    SourceIdentity,
    check_bytes,
    index_url,
    resolve_root,
    source_hash_bytes,
    source_of,
    stamp_bytes,
    stamp_files,
)

ROOT = "https://reports.example.org"
BODY = b'"""A benchmark."""\n\nimport bencher as bn\n\n\ndef bench():\n    return 1\n'


def test_hash_rule_is_the_documented_one():
    expected = hashlib.sha256(BODY).hexdigest()[:16]
    assert source_hash_bytes(BODY) == expected


def test_hash_ignores_the_report_line_wherever_it_is():
    digest = source_hash_bytes(BODY)
    assert source_hash_bytes(b"# report: https://x.example/a\n" + BODY) == digest
    assert source_hash_bytes(BODY + b"#report: anything\n") == digest
    assert source_hash_bytes(stamp_bytes(BODY, ROOT)) == digest


def test_hash_ignores_line_endings():
    digest = source_hash_bytes(BODY)
    assert source_hash_bytes(BODY.replace(b"\n", b"\r\n")) == digest
    assert source_hash_bytes(BODY.replace(b"\n", b"\r")) == digest


def test_hash_sees_code_changes_and_indented_report_text():
    digest = source_hash_bytes(BODY)
    assert source_hash_bytes(BODY.replace(b"return 1", b"return 2")) != digest
    # An indented line is code (a string, say), not a report line.
    assert source_hash_bytes(BODY + b"    # report: x\n") != digest


def test_stamp_inserts_once_and_is_idempotent():
    stamped = stamp_bytes(BODY, ROOT)
    line = f"# report: {index_url(ROOT, source_hash_bytes(BODY))}".encode()
    assert stamped.split(b"\n")[0] == line
    assert stamp_bytes(stamped, ROOT) == stamped
    assert check_bytes(stamped, ROOT) == "current"
    assert check_bytes(BODY, ROOT) == "missing"


def test_stamp_goes_after_shebang_and_coding_line():
    data = b"#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n" + BODY
    lines = stamp_bytes(data, ROOT).split(b"\n")
    assert lines[0].startswith(b"#!")
    assert b"coding" in lines[1]
    assert lines[2].startswith(b"# report: ")


def test_stamp_replaces_stale_line_and_removes_duplicates():
    data = b"# report: https://old.example/by-src/0000000000000000/index.html\n" + BODY
    data += b"# report: duplicate\n"
    assert check_bytes(data, ROOT) == "stale"
    stamped = stamp_bytes(data, ROOT)
    assert stamped.count(b"# report:") == 1
    assert check_bytes(stamped, ROOT) == "current"


def test_stamp_keeps_crlf_line_endings():
    data = BODY.replace(b"\n", b"\r\n")
    stamped = stamp_bytes(data, ROOT)
    assert b"\n" not in stamped.replace(b"\r\n", b"")
    assert check_bytes(stamped, ROOT) == "current"


def test_code_change_makes_line_stale():
    stamped = stamp_bytes(BODY, ROOT)
    assert check_bytes(stamped.replace(b"return 1", b"return 2"), ROOT) == "stale"


def test_stamp_files_check_and_only_stamped(tmp_path):
    plain = tmp_path / "plain.py"
    plain.write_bytes(BODY)
    stamped = tmp_path / "stamped.py"
    stamped.write_bytes(stamp_bytes(BODY, ROOT))

    statuses = stamp_files([plain, stamped], ROOT, check=True)
    assert [s.state for s in statuses] == ["missing", "current"]
    assert plain.read_bytes() == BODY

    statuses = stamp_files([plain, stamped], ROOT, check=True, only_stamped=True)
    assert [s.state for s in statuses] == ["unstamped", "current"]

    stamp_files([plain], ROOT)
    assert check_bytes(plain.read_bytes(), ROOT) == "current"


def test_cli_check_exit_codes(tmp_path, capsys):
    path = tmp_path / "bench.py"
    path.write_bytes(BODY)
    assert bencher_main(["stamp", "--check", "--root", ROOT, str(path)]) == 1
    assert "missing" in capsys.readouterr().err
    assert bencher_main(["stamp", "--check", "--only-stamped", "--root", ROOT, str(path)]) == 0
    # Writing exits 1 like a formatter, so a hook stops the commit.
    assert bencher_main(["stamp", "--root", ROOT, str(path)]) == 1
    assert bencher_main(["stamp", "--check", "--root", ROOT, str(path)]) == 0
    assert bencher_main(["stamp", "--check", "--root", "ftp://x", str(path)]) == 2


def test_root_resolution_order(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.bencher]\nreport_root = "https://from-config.example"\n'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(REPORT_ROOT_ENV, raising=False)
    assert resolve_root() == "https://from-config.example"
    monkeypatch.setenv(REPORT_ROOT_ENV, "https://from-env.example/")
    assert resolve_root() == "https://from-env.example"
    assert resolve_root("https://explicit.example") == "https://explicit.example"
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    monkeypatch.delenv(REPORT_ROOT_ENV)
    with pytest.raises(ValueError, match="no report root"):
        resolve_root()


@pytest.mark.parametrize(
    "root",
    ["reports.example.org", "https://user:pw@example.org", "https://example.org/?q=1", ""],
)
def test_bad_roots_are_refused(root):
    with pytest.raises(ValueError, match="report root"):
        resolve_root(root or None, env={}, start=Path("/"))


def test_source_of_functions_classes_and_instances():
    module_file = Path(sys.modules[__name__].__file__)
    identity = source_of(test_source_of_functions_classes_and_instances)
    assert identity == SourceIdentity.of_file(module_file)
    assert identity.path.endswith("test/test_source_link.py")
    assert source_of(SourceIdentity) == SourceIdentity.of_file(
        Path(sys.modules[SourceIdentity.__module__].__file__)
    )
    assert source_of(SourceIdentity("0" * 16, "x")).path.endswith("bencher/source_link.py")
    assert source_of(len) is None


def test_identity_round_trip_rejects_foreign_values():
    identity = SourceIdentity("0123456789abcdef", "pkg/bench.py")
    assert SourceIdentity.from_dict(identity.to_dict()) == identity
    assert SourceIdentity.from_dict(None) is None
    assert SourceIdentity.from_dict({"hash": "../../etc", "path": "x"}) is None
