"""Explicit publication command, separate from legacy render positional arguments."""

import argparse
import sys
from pathlib import Path

from bencher.publication_pointers import PointerFailed
from bencher.publication_target import PublicationTarget, publish_frozen_report, receipt_json
from bencher.publishing import Published, PublishFailed


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
        target = PublicationTarget(
            store=args.store,
            prefix=args.prefix,
            http_base=args.http_base,
            receipt=args.receipt,
            pointer=args.pointer,
            expiry_days=args.expiry_days,
            minimum_remaining_days=args.minimum_remaining_days,
        )
        # Persists the committed report's receipt before its separate pointer update.
        outcome = publish_frozen_report(args.directory, target)
        if isinstance(outcome, PublishFailed):
            print(
                f"publish failed: {outcome.reason} ({outcome.key or args.directory})",
                file=sys.stderr,
            )
            return 1
        assert isinstance(outcome, Published)
        print(receipt_json(outcome.receipt))
        if isinstance(outcome.pointer, PointerFailed):
            # The report is served whatever the pointer did; the exit code says
            # the deployment's current-report link is the one that is stale.
            print(
                f"report committed, pointer update failed: {outcome.pointer.reason}",
                file=sys.stderr,
            )
            return 1
    except (OSError, ValueError) as exc:
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1
    return 0
