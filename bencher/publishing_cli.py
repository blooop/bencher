"""Explicit publication command, separate from legacy render positional arguments."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from bencher.gcloud_store import GcloudStore
from bencher.object_store import LocalStore
from bencher.publication_pointers import PointerFailed
from bencher.publishing import Published, Publisher, PublishFailed


def _store(location: str, expiry_days: float | None):
    expiry = expiry_days * 86400 if expiry_days is not None else None
    if location.startswith("gs://"):
        parts = urlsplit(location)
        if parts.query or parts.fragment:
            raise ValueError("GCS store URL must not contain a query or fragment")
        return GcloudStore(parts.netloc, prefix=parts.path.strip("/"), expiry_seconds=expiry)
    if "://" in location:
        raise ValueError("store must be a local directory or gs:// URL")
    return LocalStore(location, expiry_seconds=expiry)


def _save_receipt(path: Path, data: str) -> None:
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="bencher publish", description=__doc__)
    parser.add_argument("directory", help="Frozen execution directory containing report.json")
    parser.add_argument(
        "--store", required=True, help="Local object database directory or gs:// URL"
    )
    parser.add_argument("--prefix", required=True, help="Object-key root; UUID is appended")
    parser.add_argument(
        "--http-base", required=True, help="Serving URL root; independent of storage"
    )
    parser.add_argument(
        "--receipt", type=Path, help="Also atomically persist the JSON receipt here"
    )
    parser.add_argument("--pointer", help="Optionally update an execution-time-ordered pointer key")
    parser.add_argument("--expiry-days", type=float, help="Verified backend Age Delete policy")
    parser.add_argument(
        "--minimum-remaining-days",
        type=float,
        default=0,
        help="Require this much verified lifetime before committing references",
    )
    args = parser.parse_args(argv)
    try:
        publisher = Publisher(
            _store(args.store, args.expiry_days),
            args.prefix,
            args.http_base,
            minimum_remaining_seconds=args.minimum_remaining_days * 86400,
        )
        outcome = publisher.publish(args.directory)
        if isinstance(outcome, PublishFailed):
            print(
                f"publish failed: {outcome.reason} ({outcome.key or args.directory})",
                file=sys.stderr,
            )
            return 1
        assert isinstance(outcome, Published)
        data = json.dumps(outcome.receipt.to_dict(), indent=2, allow_nan=False)
        # Persist the committed report's receipt even if its separate pointer update fails.
        if args.receipt:
            _save_receipt(args.receipt, data)
        print(data)
        if args.pointer:
            pointed = publisher.point(outcome.receipt, args.pointer)
            if isinstance(pointed, PointerFailed):
                print(f"report committed, pointer update failed: {pointed.reason}", file=sys.stderr)
                return 1
    except (OSError, ValueError) as exc:
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1
    return 0
