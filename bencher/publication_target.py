"""Where a frozen report is published, from a command line or an environment.

``bencher publish`` and the runner's inline publication resolve the same target
through this module, so a report published by a CI job and one published by hand
land under the same key and are described by the same receipt.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from bencher.publishing import CompleteReportPublisher

STORE_ENV = "BENCHER_PUBLISH_STORE"
PREFIX_ENV = "BENCHER_PUBLISH_PREFIX"
HTTP_BASE_ENV = "BENCHER_PUBLISH_HTTP_BASE"
RECEIPT_ENV = "BENCHER_PUBLISH_RECEIPT"
EXPIRY_DAYS_ENV = "BENCHER_PUBLISH_EXPIRY_DAYS"
MINIMUM_REMAINING_DAYS_ENV = "BENCHER_PUBLISH_MINIMUM_REMAINING_DAYS"

_REQUIRED = (STORE_ENV, PREFIX_ENV, HTTP_BASE_ENV)
_ALL = (*_REQUIRED, RECEIPT_ENV, EXPIRY_DAYS_ENV, MINIMUM_REMAINING_DAYS_ENV)


class PublicationFailed(RuntimeError):
    """A configured publication did not produce a verified report URL."""


def _days(value: str, name: str) -> float:
    try:
        days = float(value)
    except ValueError:
        days = -1.0
    if not math.isfinite(days) or days < 0:
        raise ValueError(f"{name} must be a number of days, not {value!r}")
    return days


@dataclass(frozen=True)
class PublicationTarget:
    """An object store to commit a frozen report to, and the root serving it.

    Storage and serving are separate namespaces on purpose: a store need not be
    served at all, and where it is, the URL root is the deployment's business.
    ``expiry_days`` describes a backend Age-based Delete policy the caller has
    already verified; ``minimum_remaining_days`` refuses to publish new
    references without that much evidenced lifetime.
    """

    store: str
    prefix: str
    http_base: str
    receipt: Path | None = None
    expiry_days: float | None = None
    minimum_remaining_days: float = 0

    def __post_init__(self) -> None:
        """Reject what no store can honour, however the target was built.

        Raises:
            ValueError: If a location is empty or a lifetime is not a usable
                number of days. Both stores reject an expiry that is not
                positive by testing ``<= 0``, which ``nan`` passes.
        """
        for name in ("store", "prefix", "http_base"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")
        if self.expiry_days is not None and not (
            math.isfinite(self.expiry_days) and self.expiry_days > 0
        ):
            raise ValueError(f"expiry_days must be positive, not {self.expiry_days!r}")
        if not (math.isfinite(self.minimum_remaining_days) and self.minimum_remaining_days >= 0):
            raise ValueError(
                f"minimum_remaining_days must be nonnegative, not {self.minimum_remaining_days!r}"
            )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PublicationTarget | None:
        """Return the configured target, or None when publication is not configured.

        Partial configuration raises instead of returning None. A store with no
        serving root publishes bytes nobody can name, and quietly doing nothing
        would hide the typo until somebody went looking for the report -- by
        which time the measurements it should have committed are gone.

        Raises:
            ValueError: If some but not all of the required variables are set,
                or a numeric variable does not hold a number of days.
        """
        source = os.environ if env is None else env
        values = {name: source.get(name, "").strip() for name in _ALL}
        if not any(values.values()):
            return None
        missing = [name for name in _REQUIRED if not values[name]]
        if missing:
            raise ValueError(
                f"publication is configured but {', '.join(missing)} "
                f"{'is' if len(missing) == 1 else 'are'} not set"
            )
        return cls(
            store=values[STORE_ENV],
            prefix=values[PREFIX_ENV],
            http_base=values[HTTP_BASE_ENV],
            receipt=Path(values[RECEIPT_ENV]) if values[RECEIPT_ENV] else None,
            expiry_days=(
                _days(values[EXPIRY_DAYS_ENV], EXPIRY_DAYS_ENV) if values[EXPIRY_DAYS_ENV] else None
            ),
            minimum_remaining_days=(
                _days(values[MINIMUM_REMAINING_DAYS_ENV], MINIMUM_REMAINING_DAYS_ENV)
                if values[MINIMUM_REMAINING_DAYS_ENV]
                else 0
            ),
        )

    def open_store(self):
        """Build the object store this target names."""
        from bencher.gcloud_store import GcloudStore
        from bencher.object_store import LocalStore

        expiry = self.expiry_days * 86400 if self.expiry_days is not None else None
        if self.store.startswith("gs://"):
            parts = urlsplit(self.store)
            if parts.query or parts.fragment:
                raise ValueError("GCS store URL must not contain a query or fragment")
            return GcloudStore(parts.netloc, prefix=parts.path.strip("/"), expiry_seconds=expiry)
        if "://" in self.store:
            raise ValueError("store must be a local directory or gs:// URL")
        return LocalStore(self.store, expiry_seconds=expiry)

    def publisher(self) -> CompleteReportPublisher:
        """Build the publisher this target describes."""
        from bencher.publishing import CompleteReportPublisher

        return CompleteReportPublisher(
            self.open_store(),
            self.prefix,
            self.http_base,
            minimum_remaining_seconds=self.minimum_remaining_days * 86400,
        )


def receipt_json(receipt) -> str:
    """Render a publication receipt as the JSON both entry points hand on."""
    return json.dumps(receipt.to_dict(), indent=2, allow_nan=False)


def save_receipt(path: Path, data: str) -> None:
    """Write *data* to *path* atomically, so a reader never sees half a receipt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def publish_frozen_report(
    directory: str | Path,
    target: PublicationTarget,
    publisher: CompleteReportPublisher | None = None,
):
    """Publish a frozen execution directory, persisting the receipt *target* names.

    Args:
        directory: A frozen execution directory containing ``report.json``.
        target: Where to commit it and where it will be served from.
        publisher: A publisher already built from *target*, when the caller needs
            it afterwards (to update a pointer, say).

    Returns:
        ``Published`` or ``PublishFailed`` -- the receipt is only persisted for
        the former, because an unpublished URL must not be left on disk.

    Raises:
        OSError: If the receipt could not be written. The message carries the
            URL of the report, which was published regardless.
    """
    from bencher.publishing import Published

    publisher = target.publisher() if publisher is None else publisher
    outcome = publisher.publish(directory)
    if isinstance(outcome, Published) and target.receipt is not None:
        try:
            save_receipt(target.receipt, receipt_json(outcome.receipt))
        except OSError as failure:
            # The bytes are committed and immutable by now, and this is the only
            # place the URL has been named.
            raise OSError(f"{outcome.url} was published, but {failure}") from failure
    return outcome


def commit_frozen_report(
    directory: str | Path,
    target: PublicationTarget,
    publisher: CompleteReportPublisher | None = None,
):
    """Publish a frozen execution directory, or raise.

    Raises:
        PublicationFailed: If the report was not committed and verified. The
            message names the directory, which ``bencher publish`` can be
            pointed at once whatever failed has been fixed.
    """
    from bencher.publishing import PublishFailed

    outcome = publish_frozen_report(directory, target, publisher)
    if isinstance(outcome, PublishFailed):
        key = f" ({outcome.key})" if outcome.key else ""
        raise PublicationFailed(f"publishing {directory} failed: {outcome.reason}{key}")
    return outcome
