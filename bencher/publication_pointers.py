"""Ordered CAS updates of a single authoritative HTML redirect object."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from bencher.complete_report import safe_path
from bencher.object_store import (
    CreateOnly,
    Match,
    ObjectStore,
    Present,
    ReadFailed,
    WriteFailed,
    Written,
)
from bencher.publishing import PublicationReceipt, http_base


@dataclass(frozen=True)
class PointerCandidate:
    """Caller-defined, comparable rank; no branch or GitHub policy in the store.

    Use a stable policy name and identically typed rank components across writers.
    Deployment callers should rank source revisions before workflow attempts.
    ``eligible`` must come from the producer's positive allowlist.
    """

    target: str
    policy: str
    rank: tuple[int | str, ...]
    eligible: bool = True

    def __post_init__(self):
        http_base(self.target)
        if (
            not self.policy
            or not self.rank
            or any(type(item) not in {int, str} for item in self.rank)
        ):
            raise ValueError("pointer requires a policy and integer/string rank components")

    @classmethod
    def for_execution(cls, receipt: PublicationReceipt) -> PointerCandidate:
        timestamp = datetime.fromisoformat(receipt.execution["executed_at"])
        return cls(
            receipt.url,
            "execution-time-uuid-v1",
            (int(timestamp.timestamp() * 1_000_000), receipt.execution["uuid"]),
        )


@dataclass(frozen=True)
class PointerUpdated:
    target: str
    version: str


@dataclass(frozen=True)
class PointerUnchanged:
    target: str | None
    reason: str


@dataclass(frozen=True)
class PointerFailed:
    reason: str


def _render(candidate: PointerCandidate) -> bytes:
    state = json.dumps(
        {
            "schema_version": 1,
            "target": candidate.target,
            "policy": candidate.policy,
            "rank": candidate.rank,
        }
    ).replace("<", "\\u003c")
    target = html.escape(candidate.target, quote=True)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={target}">'
        f'<script id="bencher-pointer" type="application/json">{state}</script>'
        f'</head><body><a href="{target}">Open current report</a></body></html>'
    ).encode()


def read_pointer(data: bytes) -> PointerCandidate:
    match = re.search(
        r'<script id="bencher-pointer" type="application/json">(.*?)</script>',
        data.decode(),
        re.DOTALL,
    )
    if not match:
        raise ValueError("object is not a bencher pointer; explicit migration is required")
    state = json.loads(match.group(1))
    if state["schema_version"] != 1:
        raise ValueError("unsupported pointer schema")
    return PointerCandidate(state["target"], state["policy"], tuple(state["rank"]))


def _compare_rank(left: tuple[int | str, ...], right: tuple[int | str, ...]) -> int:
    if len(left) != len(right):
        raise ValueError("pointer rank lengths differ")
    comparison = 0
    for a, b in zip(left, right, strict=True):
        if type(a) is not type(b):
            raise TypeError("pointer rank component types differ")
        if isinstance(a, int):
            numeric = int(b)
            difference = (a > numeric) - (a < numeric)
        else:
            text = str(b)
            difference = (a > text) - (a < text)
        if not comparison:
            comparison = difference
    return comparison


def update_pointer(  # pylint: disable=too-many-return-statements
    store: ObjectStore,
    key: str,
    candidate: PointerCandidate,
    *,
    attempts: int = 5,
    verify_target: Callable[[], str | None] | None = None,
) -> PointerUpdated | PointerUnchanged | PointerFailed:
    """Reread/reorder after CAS conflicts; fail closed on unknown existing state.

    Report callers should use ``Publisher.point`` to verify target dependencies.
    Other callers supply ``verify_target`` for their own lifetime/eligibility
    contracts. This primitive cannot infer a deployment's dependency graph.
    """
    safe_path(key)
    if attempts < 1:
        raise ValueError("pointer attempts must be positive")
    if not candidate.eligible:
        return PointerUnchanged(None, "candidate is ineligible")
    data = _render(candidate)
    for _ in range(attempts):
        current = store.read(key)
        if isinstance(current, ReadFailed):
            return PointerFailed(current.reason)
        if isinstance(current, Present):
            try:
                previous = read_pointer(current.data)
                if (
                    previous.policy != candidate.policy
                    or len(previous.rank) != len(candidate.rank)
                    or any(
                        type(a) is not type(b)
                        for a, b in zip(previous.rank, candidate.rank, strict=True)
                    )
                ):
                    return PointerFailed("pointer ordering policy or rank types differ")
                if previous.rank == candidate.rank and previous.target != candidate.target:
                    return PointerFailed("pointer identity conflict at equal ordering rank")
                if _compare_rank(previous.rank, candidate.rank) >= 0:
                    return PointerUnchanged(previous.target, "current candidate is equal or newer")
            except (ValueError, KeyError, TypeError) as exc:
                return PointerFailed(f"invalid current pointer: {exc}")
        if verify_target is not None and (reason := verify_target()):
            return PointerFailed(reason)
        condition = Match(current.version) if isinstance(current, Present) else CreateOnly()
        result = store.write(
            key, data, condition, metadata={"contentType": "text/html", "cacheControl": "no-cache"}
        )
        if isinstance(result, Written):
            return PointerUpdated(candidate.target, result.version)
        if isinstance(result, WriteFailed) and not result.outcome_unknown:
            return PointerFailed(result.reason)
    return PointerFailed("pointer CAS retry budget exhausted; candidate may require replay")
