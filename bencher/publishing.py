"""Immutable report publication. The entry page is the final commit object."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

from bencher.complete_report import safe_path, verify_report
from bencher.object_store import (
    Absent,
    CreateOnly,
    ObjectStore,
    Present,
    ReadFailed,
    WriteFailed,
)

if TYPE_CHECKING:
    from bencher.publication_pointers import PointerFailed, PointerUnchanged, PointerUpdated
    from bencher.publication_renewal import RenewalOutcome


def http_base(value: str) -> str:
    parts = urlsplit(value)
    invalid_authority = not parts.netloc or parts.username or parts.password
    invalid_suffix = parts.query or parts.fragment
    if (
        parts.scheme not in {"http", "https"}
        or invalid_authority
        or invalid_suffix
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError("HTTP base must be an absolute http(s) URL without credentials or query")
    return value.rstrip("/")


@dataclass(frozen=True)
class PublicationReceipt:
    """Stable content identity; not a promise that storage will retain it forever."""

    prefix: str
    url: str
    manifest_sha256: str
    execution: dict
    results: tuple[dict, ...]
    schema_version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> PublicationReceipt:
        """Restore a persisted receipt; verify it against storage before using its links."""
        if value.get("schema_version") != 1:
            raise ValueError("unsupported publication receipt schema")
        return cls(**{**value, "results": tuple(value["results"])})


@dataclass(frozen=True)
class Published:
    """A committed report, and what the publication then did about a pointer.

    ``publish`` never moves a pointer, so it leaves ``pointer`` None; so does a
    target that names none. ``publish_frozen_report`` fills it in, and the
    report is committed either way -- a ``PointerFailed`` here reports a stale
    redirect, never a report that was not published.

    ``renewal`` is what keeping the newly pointed-at execution alive did, and is
    filled in only where the pointer actually moved. It reports on storage
    lifetime, not on the publication, which is committed and immutable by then.
    """

    url: str
    receipt: PublicationReceipt
    pointer: PointerUpdated | PointerUnchanged | PointerFailed | None = None
    renewal: RenewalOutcome | None = None


@dataclass(frozen=True)
class PublishFailed:
    reason: str
    key: str | None = None


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CompleteReportPublisher:
    """Commits a frozen complete report directory to an object store, immutably.

    Distinct from :class:`bencher.bench_report.Publisher`, the protocol handed to
    ``bn.run(publisher=...)``: a run calls that one in-process with a live report,
    and it may do whatever a downstream project wants with it. This one takes
    a directory ``save_report`` already froze, writes every object create-only
    and reads it back, so the URL it returns names bytes that cannot change.

    Storage and HTTP roots deliberately have independent namespaces.

    ``minimum_remaining_seconds`` can require verified expiry evidence before a
    new reference is committed. Publication itself never renews old objects;
    maintenance must supply that lifetime first. Zero makes no retention promise.
    """

    def __init__(
        self,
        store: ObjectStore,
        storage_root: str,
        http_root: str,
        *,
        minimum_remaining_seconds: float = 0,
        clock=time.time,
    ) -> None:
        safe_path(storage_root)
        if minimum_remaining_seconds < 0:
            raise ValueError("minimum remaining lifetime must be nonnegative")
        self.store = store
        self.storage_root = storage_root
        self.http_root = http_base(http_root)
        self.minimum_remaining_seconds = minimum_remaining_seconds
        self.clock = clock

    def _lifetime(self, value: Present, key: str) -> PublishFailed | None:
        if self.minimum_remaining_seconds and (
            value.expires_at is None
            or value.expires_at < self.clock() + self.minimum_remaining_seconds
        ):
            return PublishFailed("required object lifetime is not verified; run maintenance", key)
        return None

    def point(self, receipt: PublicationReceipt, key: str, *, candidate=None, attempts: int = 5):
        """Point at a committed report, rechecking its dependencies before each CAS attempt."""
        from bencher.publication_pointers import PointerCandidate, update_pointer

        candidate = candidate or PointerCandidate.for_execution(receipt)
        if candidate.target != receipt.url:
            raise ValueError("pointer target does not match the publication receipt")

        def verify_target():
            outcome = self.verify(receipt)
            return outcome.reason if isinstance(outcome, PublishFailed) else None

        return update_pointer(
            self.store, key, candidate, attempts=attempts, verify_target=verify_target
        )

    def renew(self, key: str, *, attempts: int = 3):
        """Extend the lifetime of the execution the pointer at *key* currently names.

        Publication commits new bytes and never renews old ones, so under a
        backend age policy this is what keeps a pointer from outliving the report
        it redirects to. It is safe to call on a schedule and safe to call when
        nothing has been published yet.
        """
        from bencher.publication_renewal import renew_pointed_execution

        return renew_pointed_execution(
            self.store, key, self.storage_root, self.http_root, attempts=attempts
        )

    def _equal(self, value, data: bytes, key: str) -> PublishFailed | None:
        if isinstance(value, ReadFailed):
            return PublishFailed(value.reason, key)
        if isinstance(value, Absent):
            return PublishFailed("required object is absent", key)
        if value.data != data:
            return PublishFailed("immutable report identity conflict", key)
        return self._lifetime(value, key)

    def _create(self, key: str, data: bytes) -> PublishFailed | None:
        current = self.store.read(key)
        if not isinstance(current, Absent):
            return self._equal(current, data, key)
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        result = self.store.write(
            key,
            data,
            CreateOnly(),
            metadata={"contentType": content_type, "cacheControl": "public, max-age=3600"},
        )
        if isinstance(result, WriteFailed) and not result.outcome_unknown:
            return PublishFailed(result.reason, key)
        # Written, Conflict and unknown submission outcomes all require read-back.
        return self._equal(self.store.read(key), data, key)

    def publish(  # pylint: disable=too-many-return-statements
        self, directory: str | Path
    ) -> Published | PublishFailed:
        root = Path(directory)
        try:
            manifest = verify_report(root)
            manifest_bytes = (root / "report.json").read_bytes()
        except (OSError, ValueError, KeyError) as exc:
            return PublishFailed(f"invalid frozen report: {exc}")
        if json.loads(manifest_bytes) != manifest:
            return PublishFailed("frozen manifest changed during publication")
        prefix = f"{self.storage_root}/{manifest['execution']['uuid']}"
        entry = manifest["entry_page"]
        current_entry = self.store.read(f"{prefix}/{entry}")
        if isinstance(current_entry, ReadFailed):
            return PublishFailed(current_entry.reason, f"{prefix}/{entry}")
        committed = isinstance(current_entry, Present)
        inventory = {item["path"]: item for item in manifest["files"]}
        ordered = [name for name in inventory if name != entry] + ["report.json", entry]
        for name in ordered:
            key = f"{prefix}/{name}"
            try:
                data = (root / name).read_bytes()
            except OSError as exc:
                return PublishFailed(str(exc), key)
            expected = inventory.get(
                name, {"size": len(manifest_bytes), "sha256": _digest(manifest_bytes)}
            )
            if len(data) != expected["size"] or _digest(data) != expected["sha256"]:
                return PublishFailed("frozen content changed during publication", key)
            failure = (
                self._equal(self.store.read(key), data, key)
                if committed
                else self._create(key, data)
            )
            if failure:
                return failure
        receipt = PublicationReceipt(
            prefix,
            f"{self.http_root}/{manifest['execution']['uuid']}/{quote(entry, safe='/')}",
            _digest(manifest_bytes),
            manifest["execution"],
            tuple(manifest["results"]),
        )
        verified = self.verify(receipt)
        return verified if isinstance(verified, PublishFailed) else Published(receipt.url, receipt)

    def verify(  # pylint: disable=too-many-return-statements
        self, receipt: PublicationReceipt
    ) -> dict | PublishFailed:
        """Check the committed inventory, including entry bytes, before making new references."""
        safe_path(receipt.prefix)
        manifest_key = f"{receipt.prefix}/report.json"
        current = self.store.read(manifest_key)
        if not isinstance(current, Present):
            reason = current.reason if isinstance(current, ReadFailed) else "manifest is absent"
            return PublishFailed(reason, manifest_key)
        if _digest(current.data) != receipt.manifest_sha256:
            return PublishFailed("manifest identity conflict", manifest_key)
        failure = self._lifetime(current, manifest_key)
        if failure:
            return failure
        try:
            manifest = json.loads(current.data)
            expected_prefix = f"{self.storage_root}/{manifest['execution']['uuid']}"
            expected_url = (
                f"{self.http_root}/{manifest['execution']['uuid']}/"
                f"{quote(manifest['entry_page'], safe='/')}"
            )
            if receipt.prefix != expected_prefix or receipt.url != expected_url:
                return PublishFailed("receipt location does not match its manifest", manifest_key)
            if (
                manifest["schema_version"] != 1
                or manifest["execution"] != receipt.execution
                or tuple(manifest["results"]) != receipt.results
            ):
                return PublishFailed("receipt does not describe the manifest", manifest_key)
            seen = {"report.json"}
            for item in manifest["files"]:
                name = str(safe_path(item["path"]))
                if name in seen:
                    return PublishFailed("duplicate inventory path", manifest_key)
                seen.add(name)
                key = f"{receipt.prefix}/{name}"
                value = self.store.read(key)
                if not isinstance(value, Present):
                    reason = value.reason if isinstance(value, ReadFailed) else "object is absent"
                    return PublishFailed(reason, key)
                if len(value.data) != item["size"] or _digest(value.data) != item["sha256"]:
                    return PublishFailed("inventory identity conflict", key)
                failure = self._lifetime(value, key)
                if failure:
                    return failure
            if manifest["entry_page"] not in seen - {"report.json"}:
                return PublishFailed("entry page is not inventoried", manifest_key)
        except (ValueError, KeyError) as exc:
            return PublishFailed(f"invalid manifest: {exc}", manifest_key)
        return manifest
