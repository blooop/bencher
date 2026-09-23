"""Explicit publication and transfer commands, separate from legacy render arguments."""

import argparse
import sys
from pathlib import Path

from bencher.publication_pointers import PointerFailed
from bencher.publication_renewal import (
    ExecutionRenewed,
    PointerMoved,
    RenewalFailed,
    RenewalIncomplete,
)
from bencher.publication_target import (
    PublicationTarget,
    publish_frozen_report,
    receipt_json,
    renew_pointed_report,
)
from bencher.publishing import Published, PublishFailed
from bencher.report_transfer import MAX_UNPACKED_BYTES, pack_report, unpack_report


def _lifetime_diagnostic(outcome) -> str | None:
    """Return what to tell an operator about a lifetime that was not extended."""
    if isinstance(outcome, RenewalFailed):
        return f"{outcome.reason} ({outcome.key})" if outcome.key else outcome.reason
    if isinstance(outcome, RenewalIncomplete):
        refused = ", ".join(f"{item.key}: {item.reason}" for item in outcome.refused)
        return f"{len(outcome.renewed)} objects renewed, {len(outcome.refused)} refused: {refused}"
    return None


def _renewal_summary(outcome) -> str:
    """Return what an operator should read on a renewal that asks nothing of them."""
    if isinstance(outcome, ExecutionRenewed):
        return f"renewed {len(outcome.keys)} objects of {outcome.target}"
    if isinstance(outcome, PointerMoved):
        return f"renewed {outcome.renewed}; the pointer now names {outcome.current}"
    return f"nothing renewed: {outcome.reason}"


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
        if diagnostic := _lifetime_diagnostic(outcome.renewal):
            # The report is committed and the pointer moved; what is wrong is
            # that the bytes the pointer now names may be reaped under the
            # store's age policy while the pointer still names them.
            print(f"report committed, renewal failed: {diagnostic}", file=sys.stderr)
            return 1
    except (OSError, ValueError) as exc:
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1
    return 0


def renew_main(argv: list[str]) -> int:
    """Renew the execution a pointer names, between publications.

    Publication only renews what it has just made current, so a deployment whose
    store deletes by age runs this on a schedule as well.
    """
    parser = argparse.ArgumentParser(prog="bencher renew", description=renew_main.__doc__)
    parser.add_argument(
        "--store", required=True, help="Local object database directory or gs:// URL"
    )
    parser.add_argument("--prefix", required=True, help="Object-key root; UUID is appended")
    parser.add_argument(
        "--http-base", required=True, help="Serving URL root; independent of storage"
    )
    parser.add_argument("--pointer", required=True, help="Pointer key naming the current report")
    parser.add_argument("--expiry-days", type=float, help="Verified backend Age Delete policy")
    args = parser.parse_args(argv)
    try:
        outcome = renew_pointed_report(
            PublicationTarget(
                store=args.store,
                prefix=args.prefix,
                http_base=args.http_base,
                pointer=args.pointer,
                expiry_days=args.expiry_days,
            )
        )
    except (OSError, ValueError) as exc:
        print(f"renew failed: {exc}", file=sys.stderr)
        return 1
    if diagnostic := _lifetime_diagnostic(outcome):
        print(f"renew failed: {diagnostic}", file=sys.stderr)
        return 1
    print(_renewal_summary(outcome))
    return 0


def pack_main(argv: list[str]) -> int:
    """Pack a frozen execution directory into one archive file.

    The machine that measured is often not the machine that may publish. This
    writes the one object a transfer moves; how it travels is the caller's.
    """
    parser = argparse.ArgumentParser(prog="bencher pack", description=pack_main.__doc__)
    parser.add_argument("directory", help="Frozen execution directory containing report.json")
    parser.add_argument("archive", help="Archive file to write; it must not already exist")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_UNPACKED_BYTES,
        help="Refuse a report larger than this, as unpacking would",
    )
    args = parser.parse_args(argv)
    try:
        packed = pack_report(args.directory, args.archive, max_bytes=args.max_bytes)
    except (OSError, ValueError) as exc:
        print(f"pack failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"packed {packed.files} files of {packed.execution} "
        f"into {packed.archive}; sha256 {packed.sha256}"
    )
    return 0


def unpack_main(argv: list[str]) -> int:
    """Unpack a report archive into a new directory and verify it.

    The result is publishable as it stands: run ``bencher publish`` on it. An
    archive is untrusted input, and an unpack that refuses anything writes
    nothing.
    """
    parser = argparse.ArgumentParser(prog="bencher unpack", description=unpack_main.__doc__)
    parser.add_argument("archive", help="Archive file written by bencher pack")
    parser.add_argument("directory", help="Directory to write; it must not already exist")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_UNPACKED_BYTES,
        help="Refuse an archive that expands past this, before writing anything",
    )
    args = parser.parse_args(argv)
    try:
        unpacked = unpack_report(args.archive, args.directory, max_bytes=args.max_bytes)
    except (OSError, ValueError) as exc:
        print(f"unpack failed: {exc}", file=sys.stderr)
        return 1
    print(f"unpacked {unpacked.files} files of {unpacked.execution} into {unpacked.directory}")
    return 0
