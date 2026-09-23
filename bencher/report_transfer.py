"""Pack and unpack a frozen execution report for transfer between machines.

The machine that measures is often not the machine that may publish: a device
running a benchmark has no credentials for the object store, and the host that
has them never ran the benchmark. So the frozen directory has to move.

Moving it with a recursive copy is what ``verify_report`` was written to catch.
The inventory in ``report.json`` names every file with its size and digest and
accepts nothing else, so a copy that filters by modification time, merges into a
shared directory, or simply lets something else write alongside produces a
directory its own inventory rightly refuses -- and the refusal arrives at
publication time, on the machine that cannot run the benchmark again.

Packing makes the transfer one object instead of a directory tree, and unpacking
verifies what it wrote before it hands the directory over. How the one object
travels -- ssh, a bucket, a courier with a disk -- is the caller's business and
none of bencher's.

The archive is an uncompressed-metadata gzip tar, and the choice is about what
survives the crossing rather than about size. Tar is a stream of self-describing
headers with no offsets into the file, so nothing in it depends on the
filesystem, the architecture or the byte order it was written on; gzip is the
one compressor available everywhere. Every member is normalised -- sorted by
path, mode 0644, mtime 0, no owner, no directory entries -- and the gzip header
records neither a name nor a time, so packing the same directory twice produces
the same bytes. That is a convenience for caching and deduplication, not the
correctness argument: the report's identity is ``report.json``, which travels
inside the archive and is checked against the bytes that were written on the
other side. Compare digests of files, not of archives; the deflate stream is
reproducible for a given zlib build and bencher does not promise more than that.

Treat every archive as untrusted input. Unpacking refuses absolute paths, ``..``
components, symlinks, hard links, device nodes, anything that is not a regular
file, any member the inventory does not list, and an archive that expands past
``max_bytes``. Nothing is written until every member has passed.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bencher.complete_report import file_digest, safe_path, verify_report

# What one archive may expand to, and how many files it may hold. A frozen report
# is HTML, JSON and whatever media the sweep recorded, so these bound a hostile
# archive rather than a real one; both are arguments for the report that needs
# more room.
MAX_UNPACKED_BYTES = 4 * 1024**3
MAX_MEMBERS = 65536

# The inventory is read into memory before anything is extracted, so it is capped
# separately and far lower than the payload it describes.
MAX_MANIFEST_BYTES = 64 * 1024**2

_COMPRESSION_LEVEL = 6


@dataclass(frozen=True)
class ReportPacked:
    """One frozen execution sealed into one file, verified immediately before.

    ``sha256`` is the archive's own digest. It is there so a transfer can prove
    it moved the file intact, and it is not the report's identity: that is
    ``report.json``, which travels inside and which unpacking checks against
    every byte it writes.
    """

    archive: Path
    execution: str
    files: int
    size: int
    sha256: str


@dataclass(frozen=True)
class ReportUnpacked:
    """A frozen execution restored from an archive and verified where it landed.

    The directory is publishable as it stands: ``commit_frozen_report`` and
    ``bencher publish`` ask for nothing that unpacking has not already done.
    """

    directory: Path
    execution: str
    files: int
    size: int


class _Hashed:
    """Digest a member as the archive takes it, so the two cannot disagree."""

    def __init__(self, stream) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def _member(name: str, size: int) -> tarfile.TarInfo:
    """Describe a member by its content alone, so two packs agree byte for byte."""
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = 0
    info.mode = 0o644
    info.type = tarfile.REGTYPE
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _inventory(manifest: dict) -> dict[str, dict]:
    """Return the inventory keyed by path, with the manifest itself included."""
    return {str(safe_path(item["path"])): item for item in manifest["files"]}


def _deflate(raw) -> gzip.GzipFile:
    """Compress recording neither the staging file's name nor the time of day.

    Both are what a gzip header carries by default, and both would make two
    packs of one directory differ.
    """
    return gzip.GzipFile(
        fileobj=raw, filename="", mode="wb", compresslevel=_COMPRESSION_LEVEL, mtime=0
    )


def _write_archive(root: Path, names: list[str], inventory: dict[str, dict], path: Path) -> None:
    """Write every named file into a normalised tar, checking it against the inventory."""
    with (
        path.open("wb") as raw,
        _deflate(raw) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for name in names:
            item = inventory[name]
            with (root / name).open("rb") as stream:
                source = _Hashed(stream)
                tar.addfile(_member(name, item["size"]), source)
            if source.digest.hexdigest() != item["sha256"]:
                raise ValueError(f"frozen content changed while packing: {name}")


def pack_report(
    directory: str | Path, archive: str | Path, *, max_bytes: int = MAX_UNPACKED_BYTES
) -> ReportPacked:
    """Pack a verified frozen execution directory into one archive file.

    The directory is verified first: there is no point sealing bytes that
    already fail their own inventory, because the machine that unpacks them
    cannot fix them. What the archive holds is exactly what the inventory lists,
    read again as it is written.

    Args:
        directory: A frozen execution directory containing ``report.json``.
        archive: The file to write. It must not exist; a frozen execution is
            immutable and overwriting one silently is not a transfer.
        max_bytes: Refuse a report larger than this, which is the size the far
            side would have to refuse instead.

    Returns:
        A ``ReportPacked`` naming the archive, the execution and the digest of
        the file that was written.

    Raises:
        ValueError: If the directory fails ``verify_report``, if its contents
            changed while they were being read, if the archive path is taken,
            or if the report is past ``max_bytes`` or ``MAX_MEMBERS`` files.
        OSError: If a file could not be read or the archive could not be written.
    """
    root = Path(directory)
    destination = Path(archive)
    manifest = verify_report(root)
    inventory = _inventory(manifest)
    inventory["report.json"] = {
        "path": "report.json",
        "size": (root / "report.json").stat().st_size,
        "sha256": file_digest(root / "report.json"),
    }
    names = ["report.json"] + sorted(name for name in inventory if name != "report.json")
    total = sum(inventory[name]["size"] for name in names)
    if len(names) > MAX_MEMBERS:
        raise ValueError(f"frozen report holds more than {MAX_MEMBERS} files")
    if total > max_bytes:
        raise ValueError(f"frozen report is larger than {max_bytes} bytes")
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"archive already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, staging = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}-")
    os.close(handle)
    staged = Path(staging)
    try:
        _write_archive(root, names, inventory, staged)
        digest = file_digest(staged)
        # Linking publishes the name atomically and fails rather than replacing
        # an archive another packer wrote between the check above and here.
        try:
            os.link(staged, destination)
        except FileExistsError as exc:
            raise ValueError(f"archive already exists: {destination}") from exc
    finally:
        staged.unlink(missing_ok=True)
    return ReportPacked(
        archive=destination,
        execution=manifest["execution"]["uuid"],
        files=len(names),
        size=total,
        sha256=digest,
    )


def _members(tar: tarfile.TarFile, max_bytes: int) -> tuple[list[tarfile.TarInfo], int]:
    """Read the headers, refusing anything that is not a plain file in the tree."""
    members: list[tarfile.TarInfo] = []
    names: set[str] = set()
    total = 0
    for member in tar:
        if not member.isreg():
            raise ValueError(f"archive member is not a regular file: {member.name}")
        name = str(safe_path(member.name))
        if name in names:
            raise ValueError(f"duplicate archive member: {name}")
        names.add(name)
        total += member.size
        if len(members) >= MAX_MEMBERS:
            raise ValueError(f"archive holds more than {MAX_MEMBERS} files")
        if total > max_bytes:
            raise ValueError(f"archive expands to more than {max_bytes} bytes")
        # The far side's ownership and permissions are nobody's business here.
        member.mode = 0o644
        members.append(member)
    return members, total


def _listed(tar: tarfile.TarFile, members: list[tarfile.TarInfo]) -> set[str]:
    """Return the paths the archived inventory lists, including itself."""
    entry = next((member for member in members if member.name == "report.json"), None)
    if entry is None:
        raise ValueError("archive holds no report.json")
    if entry.size > MAX_MANIFEST_BYTES:
        raise ValueError(f"archived inventory is larger than {MAX_MANIFEST_BYTES} bytes")
    stream = tar.extractfile(entry)
    if stream is None:
        raise ValueError("archived inventory could not be read")
    try:
        manifest = json.loads(stream.read().decode("utf-8"))
        return {"report.json"} | {str(safe_path(item["path"])) for item in manifest["files"]}
    except (KeyError, TypeError, UnicodeDecodeError) as exc:
        raise ValueError(f"archived inventory is unreadable: {exc}") from exc


def _extract(archive: Path, staging: Path, max_bytes: int) -> int:
    """Refuse every member that fails a check, then write the ones that passed."""
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members, total = _members(tar, max_bytes)
            listed = _listed(tar, members)
            written = {member.name for member in members}
            if written != listed:
                unlisted = sorted(written - listed)
                missing = sorted(listed - written)
                raise ValueError(
                    f"archive does not match its inventory; unlisted {unlisted}, missing {missing}"
                )
            # Every member has already been checked by hand. The extraction
            # filter is the second reading of the same refusals, by the library.
            tar.extractall(staging, members=members, filter="data")
    except (tarfile.TarError, EOFError, gzip.BadGzipFile) as exc:
        raise ValueError(f"unreadable report archive: {exc}") from exc
    return total


def unpack_report(
    archive: str | Path, directory: str | Path, *, max_bytes: int = MAX_UNPACKED_BYTES
) -> ReportUnpacked:
    """Unpack an archive into a new directory and verify what was written.

    Every archive is treated as untrusted input. Members are checked before
    anything is written, the extraction happens beside the destination, and the
    result has to pass ``verify_report`` before it is moved into place -- so a
    failed unpack leaves no directory behind and a published report is never a
    partially trusted one.

    Args:
        archive: A file written by ``pack_report``.
        directory: Where the frozen execution is written. It must not exist:
            unpacking into an existing directory is the merge that inventories
            were written to refuse.
        max_bytes: Refuse an archive that expands past this, before writing.

    Returns:
        A ``ReportUnpacked`` naming the verified directory, which
        ``commit_frozen_report`` can publish as it stands.

    Raises:
        ValueError: If the archive is unreadable, holds anything that is not a
            plain file inside the destination, holds a file its inventory does
            not list, expands past ``max_bytes``, or fails verification once
            written. Also if the destination already exists.
        OSError: If the archive could not be read or the destination written.
    """
    source = Path(archive)
    destination = Path(directory)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"unpack destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}-"))
    try:
        total = _extract(source, staging, max_bytes)
        manifest = verify_report(staging)
        files = len(manifest["files"]) + 1
        staging.rename(destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return ReportUnpacked(
        directory=destination,
        execution=manifest["execution"]["uuid"],
        files=files,
        size=total,
    )
