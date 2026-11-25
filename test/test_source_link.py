"""The source hash rule and the ``bencher stamp`` command."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from bencher.render import main as bencher_main
from bencher.source_link import (
    REPORT_KEY_ENV,
    REPORT_ROOT_ENV,
    SourceIdentity,
    check_bytes,
    index_url,
    path_from_line,
    path_index_url,
    path_report_line,
    resolve_key,
    resolve_root,
    safe_source_path,
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


# --- path mode -------------------------------------------------------------------------

PATH = "ros/pkg/bench_x.py"


def repo(tmp_path: Path) -> Path:
    """A git checkout with one bench file at PATH; returns the file."""
    (tmp_path / ".git").mkdir()
    path = tmp_path / PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(BODY)
    return path


def test_path_line_names_the_by_path_page():
    assert path_index_url(ROOT + "/", PATH) == f"{ROOT}/by-path/{PATH}/index.html"
    assert path_report_line(ROOT, PATH) == f"# report: {ROOT}/by-path/{PATH}/index.html"
    stamped = stamp_bytes(BODY, ROOT, "path", PATH)
    assert stamped.split(b"\n")[0] == path_report_line(ROOT, PATH).encode()
    assert check_bytes(stamped, ROOT, "path", PATH) == "current"
    assert check_bytes(BODY, ROOT, "path", PATH) == "missing"


def test_an_edit_does_not_change_the_path_line():
    stamped = stamp_bytes(BODY, ROOT, "path", PATH)
    edited = stamped.replace(b"return 1", b"return 2")
    assert check_bytes(edited, ROOT, "path", PATH) == "current"
    assert stamp_bytes(edited, ROOT, "path", PATH) == edited
    # The hash still sees the edit, so by-src pages stay per version.
    assert source_hash_bytes(edited) != source_hash_bytes(stamped)


def test_path_check_catches_a_renamed_copied_or_doubled_line():
    stamped = stamp_bytes(BODY, ROOT, "path", PATH)
    assert check_bytes(stamped, ROOT, "path", "ros/pkg/bench_y.py") == "stale"
    assert check_bytes(stamped + b"# report: extra\n", ROOT, "path", PATH) == "stale"
    # A hash line is stale in path mode and a path line is stale in hash mode.
    assert check_bytes(stamp_bytes(BODY, ROOT), ROOT, "path", PATH) == "stale"
    assert check_bytes(stamped, ROOT) == "stale"


def test_stamp_files_in_path_mode_uses_the_git_root(tmp_path):
    path = repo(tmp_path)
    [status] = stamp_files([path], ROOT, key="path")
    assert status.state == "missing"
    assert status.expected == path_report_line(ROOT, PATH)
    assert path.read_bytes().startswith(path_report_line(ROOT, PATH).encode())
    [status] = stamp_files([path], ROOT, check=True, key="path")
    assert status.state == "current"

    moved = tmp_path / "ros" / "pkg" / "bench_y.py"
    path.rename(moved)
    [status] = stamp_files([moved], ROOT, check=True, key="path")
    assert status.state == "stale"
    assert status.expected == path_report_line(ROOT, "ros/pkg/bench_y.py")


def test_path_mode_refuses_a_file_outside_a_repository(tmp_path):
    path = tmp_path / "bench.py"
    path.write_bytes(BODY)
    with pytest.raises(ValueError, match="git repository"):
        stamp_files([path], ROOT, key="path")


def test_cli_key_flag(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(REPORT_KEY_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    path = repo(tmp_path)
    assert bencher_main(["stamp", "--key", "path", "--root", ROOT, str(path)]) == 1
    assert bencher_main(["stamp", "--check", "--key", "path", "--root", ROOT, str(path)]) == 0
    path.write_bytes(path.read_bytes().replace(b"return 1", b"return 2"))
    assert bencher_main(["stamp", "--check", "--key", "path", "--root", ROOT, str(path)]) == 0
    # The same file is stale in hash mode, the default.
    assert bencher_main(["stamp", "--check", "--root", ROOT, str(path)]) == 1
    assert "--key hash" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        bencher_main(["stamp", "--key", "name", "--root", ROOT, str(path)])


def test_key_resolution_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(REPORT_KEY_ENV, raising=False)
    assert resolve_key() == "hash"
    monkeypatch.setenv(REPORT_KEY_ENV, "path")
    assert resolve_key() == "path"
    (tmp_path / "pyproject.toml").write_text('[tool.bencher]\nreport_key = "hash"\n')
    assert resolve_key() == "hash"  # The repository's setting beats the environment.
    (tmp_path / "pyproject.toml").write_text('[tool.bencher]\nreport_key = "path"\n')
    monkeypatch.delenv(REPORT_KEY_ENV)
    assert resolve_key() == "path"
    assert resolve_key("hash") == "hash"
    with pytest.raises(ValueError, match="report key"):
        resolve_key("content")


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/abs/bench.py",
        "a//b.py",
        "a/./b.py",
        "../b.py",
        "a/../../b.py",
        "a/",
        "a b.py",
        "a\tb.py",
        "a\nb.py",
        "a\\b.py",
        "a?b.py",
        "a%2e.py",
        "\u00e9t\u00e9.py",
        "a/b.py\n",
    ],
)
def test_unsafe_paths_are_refused(path):
    with pytest.raises(ValueError, match="source path"):
        safe_source_path(path)
    with pytest.raises(ValueError, match="source path"):
        path_report_line(ROOT, path)


def test_safe_paths_pass():
    for path in ["bench.py", PATH, "a/b-c_d.e+f@g.py", ".hidden/x.py"]:
        assert safe_source_path(path) == path


def test_path_from_line_reads_only_valid_by_path_lines():
    assert path_from_line(stamp_bytes(BODY, ROOT, "path", PATH)) == PATH
    assert path_from_line(stamp_bytes(BODY, "https://r.example/sub/dir", "path", PATH)) == PATH
    assert path_from_line(BODY) is None
    assert path_from_line(stamp_bytes(BODY, ROOT)) is None  # A hash line names no path.
    assert path_from_line(b"# report: https://r.example/by-path/../x.py/index.html\n") is None
    assert path_from_line(b"# report: https://r.example/by-path//x.py/index.html\n") is None
    assert path_from_line(b"# report: file:///by-path/x.py/index.html\n") is None


def test_a_file_with_no_git_root_takes_its_path_from_the_line(tmp_path):
    # An install tree or Bazel runfiles: no .git above the file.
    path = tmp_path / "install" / "lib" / "bench_x.py"
    path.parent.mkdir(parents=True)
    path.write_bytes(stamp_bytes(BODY, ROOT, "path", PATH))
    identity = SourceIdentity.of_file(path)
    assert identity == SourceIdentity(source_hash_bytes(BODY), PATH)

    # Without a by-path line, or with an unsafe one, the bare file name as before.
    path.write_bytes(stamp_bytes(BODY, ROOT))
    assert SourceIdentity.of_file(path).path == "bench_x.py"
    path.write_bytes(b"# report: https://r.example/by-path/../../x.py/index.html\n" + BODY)
    assert SourceIdentity.of_file(path).path == "bench_x.py"


def test_source_of_a_module_in_a_tree_with_no_git(tmp_path, monkeypatch):
    # A bench module that Bazel runfiles hold: its file has a path line, no .git.
    module = tmp_path / "runfiles" / "bench_x.py"
    module.parent.mkdir()
    module.write_bytes(stamp_bytes(BODY, ROOT, "path", PATH))
    monkeypatch.setattr("bencher.source_link.inspect.getsourcefile", lambda _: str(module))
    identity = source_of(test_source_of_a_module_in_a_tree_with_no_git)
    assert identity == SourceIdentity(source_hash_bytes(BODY), PATH)


def test_hash_mode_unchanged_by_path_mode():
    # The 2.2.0 calls and lines, byte for byte.
    assert stamp_bytes(BODY, ROOT) == stamp_bytes(BODY, ROOT, "hash")
    assert check_bytes(stamp_bytes(BODY, ROOT), ROOT) == "current"
    assert index_url(ROOT, "0123456789abcdef") == f"{ROOT}/by-src/0123456789abcdef/index.html"
