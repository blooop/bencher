"""A frozen execution travels as one file, and arrives as the same bytes or not at all."""

from __future__ import annotations

import gzip
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.publication_target import PublicationTarget, commit_frozen_report
from bencher.publishing import Published
from bencher.report_transfer import (
    MAX_UNPACKED_BYTES,
    ReportPacked,
    pack_report,
    unpack_report,
)

pytest_plugins = ["test.test_publishing"]


def write_archive(report: Path, path: Path, *, extra=(), replace=None, skip=()) -> Path:
    """Write an archive of *report*, plus whatever a test needs it to get wrong."""
    replace = replace or {}
    with (
        path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for file in sorted(report.rglob("*")):
            name = file.relative_to(report).as_posix()
            if not file.is_file() or name in skip:
                continue
            data = replace.get(name, file.read_bytes())
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info, data in extra:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


def contents(root: Path) -> dict[str, bytes]:
    """Every file under *root*, by relative path."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def member(name: str, kind: bytes, *, linkname: str = "") -> tuple[tarfile.TarInfo, None]:
    """Describe an archive member that is not a plain file."""
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = linkname
    return info, None


def publish(directory: Path, tmp_path: Path):
    return commit_frozen_report(
        directory,
        PublicationTarget(
            store=str(tmp_path / "store"),
            prefix="reports/transfer",
            http_base="https://reports.example.test/bench",
        ),
    )


def test_a_packed_report_unpacks_to_a_publishable_directory(report, tmp_path):
    """The whole point: the machine with the credentials never ran the benchmark."""
    packed = pack_report(report, tmp_path / "transfer.tar.gz")
    assert isinstance(packed, ReportPacked)
    assert packed.archive.is_file()
    assert packed.files == len(bn.verify_report(report)["files"]) + 1
    unpacked = unpack_report(packed.archive, tmp_path / "arrived")
    assert unpacked.execution == packed.execution
    manifest = bn.verify_report(unpacked.directory)
    assert manifest == json.loads((report / "report.json").read_text())
    outcome = publish(unpacked.directory, tmp_path)
    assert isinstance(outcome, Published)
    assert outcome.url.endswith(f"/{unpacked.execution}/index.html")


def test_a_rendered_report_crosses_intact(tmp_path, monkeypatch):
    """Against what save_report really writes, whose asset paths are long and nested."""
    monkeypatch.chdir(tmp_path)
    bench = bn.Bench("transfer", ExampleBenchCfg())
    try:
        with bn.execution_context(reproduce_command="pixi run transfer-bench"):
            result = bench.collect(
                input_vars=[ExampleBenchCfg.param.theta],
                result_vars=[ExampleBenchCfg.param.out_sin],
                run_cfg=bn.BenchRunCfg(),
            )
    finally:
        bench.close()
    entry = bn.render_report(result, tmp_path / "reports", complete=True)
    packed = pack_report(entry.parent, tmp_path / "transfer.tar.gz")
    arrived = unpack_report(packed.archive, tmp_path / "arrived")
    manifest = bn.verify_report(arrived.directory)
    assert manifest["execution"]["reproduce_command"] == "pixi run transfer-bench"
    assert arrived.files == packed.files
    assert isinstance(publish(arrived.directory, tmp_path), Published)


def test_unpacking_reproduces_every_byte_and_no_others(report, tmp_path):
    packed = pack_report(report, tmp_path / "transfer.tar.gz")
    arrived = unpack_report(packed.archive, tmp_path / "arrived").directory
    assert contents(arrived) == contents(report)


def test_packing_refuses_a_directory_that_fails_its_own_inventory(report, tmp_path):
    """Sealing an unverifiable directory only moves the failure to the far machine."""
    (report / "stray.txt").write_text("added alongside")
    with pytest.raises(ValueError):
        pack_report(report, tmp_path / "transfer.tar.gz")
    assert not (tmp_path / "transfer.tar.gz").exists()


def test_packing_the_same_directory_twice_gives_the_same_bytes(report, tmp_path):
    """Member metadata is normalised, so the archive says nothing about its machine."""
    first = pack_report(report, tmp_path / "first.tar.gz")
    (report / "index.html").chmod(0o600)
    os.utime(report / "index.html", (0, 0))
    second = pack_report(report, tmp_path / "second.tar.gz")
    assert first.archive.read_bytes() == second.archive.read_bytes()
    assert first.sha256 == second.sha256


def test_an_archive_carries_no_ownership_times_or_directories(report, tmp_path):
    packed = pack_report(report, tmp_path / "transfer.tar.gz")
    with tarfile.open(packed.archive, "r:gz") as tar:
        members = tar.getmembers()
    names = [m.name for m in members]
    assert names[0] == "report.json", "the inventory is readable before the payload"
    assert names[1:] == sorted(names[1:])
    assert all(m.isreg() for m in members)
    assert {(m.mtime, m.mode, m.uid, m.gid, m.uname, m.gname) for m in members} == {
        (0, 0o644, 0, 0, "", "")
    }


def test_packing_refuses_an_archive_path_that_is_taken(report, tmp_path):
    archive = tmp_path / "transfer.tar.gz"
    pack_report(report, archive)
    before = archive.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        pack_report(report, archive)
    assert archive.read_bytes() == before


def test_packing_refuses_a_report_past_the_cap(report, tmp_path):
    with pytest.raises(ValueError, match="larger than"):
        pack_report(report, tmp_path / "transfer.tar.gz", max_bytes=8)
    assert not (tmp_path / "transfer.tar.gz").exists()


def test_unpacking_refuses_an_existing_destination(report, tmp_path):
    """A frozen execution is immutable, and merging into one is what inventories catch."""
    packed = pack_report(report, tmp_path / "transfer.tar.gz")
    destination = tmp_path / "arrived"
    destination.mkdir()
    (destination / "keep.txt").write_text("not ours to remove")
    with pytest.raises(ValueError, match="already exists"):
        unpack_report(packed.archive, destination)
    assert (destination / "keep.txt").read_text() == "not ours to remove"


def test_unpacking_refuses_a_tampered_member(report, tmp_path):
    """Same length, different bytes: only the inventory digest catches this."""
    entry = (report / "index.html").read_bytes()
    archive = write_archive(
        report, tmp_path / "tampered.tar.gz", replace={"index.html": b"x" * len(entry)}
    )
    with pytest.raises(ValueError, match="digest mismatch"):
        unpack_report(archive, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_a_file_the_inventory_does_not_list(report, tmp_path):
    archive = write_archive(
        report, tmp_path / "extra.tar.gz", extra=[(tarfile.TarInfo("notes.txt"), b"hi")]
    )
    with pytest.raises(ValueError, match="unlisted"):
        unpack_report(archive, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_an_archive_missing_an_inventoried_file(report, tmp_path):
    archive = write_archive(report, tmp_path / "short.tar.gz", skip={"summary.json"})
    with pytest.raises(ValueError, match="missing"):
        unpack_report(archive, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_an_archive_without_an_inventory(report, tmp_path):
    archive = write_archive(report, tmp_path / "blind.tar.gz", skip={"report.json"})
    with pytest.raises(ValueError, match="no report.json"):
        unpack_report(archive, tmp_path / "arrived")


@pytest.mark.parametrize(
    "name",
    ["/etc/cron.d/evil", "../escaped", "nested/../../escaped", "a\\b", "./index.html"],
)
def test_unpacking_refuses_a_member_that_leaves_the_destination(report, tmp_path, name):
    """safe_path is the one path check, and it runs before anything is written."""
    info = tarfile.TarInfo(name)
    info.size = 4
    archive = write_archive(report, tmp_path / "escape.tar.gz", extra=[(info, b"evil")])
    with pytest.raises(ValueError, match="unsafe inventory path"):
        unpack_report(archive, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()
    assert not Path("/etc/cron.d/evil").exists()


@pytest.mark.parametrize(
    ("kind", "linkname"),
    [
        (tarfile.SYMTYPE, "/etc/passwd"),
        (tarfile.LNKTYPE, "report.json"),
        (tarfile.CHRTYPE, ""),
        (tarfile.BLKTYPE, ""),
        (tarfile.FIFOTYPE, ""),
        (tarfile.DIRTYPE, ""),
    ],
)
def test_unpacking_refuses_anything_that_is_not_a_regular_file(report, tmp_path, kind, linkname):
    """Including a directory member: directories come from the paths, never from a header."""
    archive = write_archive(
        report, tmp_path / "odd.tar.gz", extra=[member("payload", kind, linkname=linkname)]
    )
    with pytest.raises(ValueError, match="not a regular file"):
        unpack_report(archive, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_an_archive_that_expands_past_the_cap(report, tmp_path):
    """Declared sizes are read from the headers, so nothing is written to find this out."""
    packed = pack_report(report, tmp_path / "transfer.tar.gz")
    with pytest.raises(ValueError, match="expands to more than"):
        unpack_report(packed.archive, tmp_path / "arrived", max_bytes=16)
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_a_duplicate_member(report, tmp_path):
    info = tarfile.TarInfo("index.html")
    info.size = 5
    archive = write_archive(report, tmp_path / "twice.tar.gz", extra=[(info, b"again")])
    with pytest.raises(ValueError, match="duplicate archive member"):
        unpack_report(archive, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_a_file_that_is_not_an_archive(tmp_path):
    (tmp_path / "junk.tar.gz").write_bytes(b"not an archive at all")
    with pytest.raises(ValueError, match="unreadable report archive"):
        unpack_report(tmp_path / "junk.tar.gz", tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_unpacking_refuses_a_truncated_archive(report, tmp_path):
    packed = pack_report(report, tmp_path / "transfer.tar.gz")
    truncated = tmp_path / "half.tar.gz"
    truncated.write_bytes(packed.archive.read_bytes()[: packed.archive.stat().st_size // 2])
    with pytest.raises(ValueError):
        unpack_report(truncated, tmp_path / "arrived")
    assert not (tmp_path / "arrived").exists()


def test_the_cap_is_a_default_and_not_a_limit_on_real_reports(report, tmp_path):
    packed = pack_report(report, tmp_path / "transfer.tar.gz", max_bytes=MAX_UNPACKED_BYTES)
    assert packed.size < MAX_UNPACKED_BYTES


def test_the_cli_moves_a_report_between_two_directories(report, tmp_path, capsys):
    """One command on the machine that measured, one on the machine that publishes."""
    archive = tmp_path / "transfer.tar.gz"
    assert bn.render.main(["pack", str(report), str(archive)]) == 0
    assert "sha256" in capsys.readouterr().out
    assert bn.render.main(["unpack", str(archive), str(tmp_path / "arrived")]) == 0
    assert str(tmp_path / "arrived") in capsys.readouterr().out
    assert isinstance(publish(tmp_path / "arrived", tmp_path), Published)


def test_the_cli_reports_a_refusal_without_a_traceback(report, tmp_path, capsys):
    assert bn.render.main(["pack", str(tmp_path / "absent"), str(tmp_path / "a.tar.gz")]) == 1
    assert "pack failed" in capsys.readouterr().err
    archive = pack_report(report, tmp_path / "transfer.tar.gz").archive
    assert bn.render.main(["unpack", str(archive), str(archive)]) == 1
    assert "unpack failed" in capsys.readouterr().err
