"""Small conditional remote-object contract, independent of the benchmark cache.

Versions and pagination tokens are opaque to consumers. Expected I/O failures are
values; invalid arguments and programming errors are not suppressed.
"""

from __future__ import annotations

import base64
import json
import sqlite3
import time
from collections.abc import Callable, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from bencher.complete_report import safe_path


@dataclass(frozen=True)
class Present:
    data: bytes
    version: str
    metadata: dict = field(default_factory=dict)
    created_at: float | None = None
    expires_at: float | None = None


@dataclass(frozen=True)
class Absent:
    pass


@dataclass(frozen=True)
class ReadFailed:
    reason: str


@dataclass(frozen=True)
class CreateOnly:
    pass


@dataclass(frozen=True)
class Match:
    version: str


@dataclass(frozen=True)
class Written:
    version: str


@dataclass(frozen=True)
class Conflict:
    pass


@dataclass(frozen=True)
class WriteFailed:
    reason: str
    outcome_unknown: bool


@dataclass(frozen=True)
class Renewed:
    version: str
    created_at: float
    expires_at: float | None


@dataclass(frozen=True)
class Unsupported:
    reason: str


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    version: str
    created_at: float | None
    expires_at: float | None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Listed:
    items: tuple[ObjectInfo, ...]
    next_token: str | None

    @property
    def complete(self) -> bool:
        return self.next_token is None


@dataclass(frozen=True)
class ListFailed:
    reason: str


class ObjectStore(Protocol):
    def read(self, key: str) -> Present | Absent | ReadFailed: ...

    def write(
        self,
        key: str,
        data: bytes,
        condition: CreateOnly | Match,
        *,
        metadata: Mapping | None = None,
    ) -> Written | Conflict | WriteFailed: ...

    def list(
        self, prefix: str = "", *, token: str | None = None, limit: int = 1000
    ) -> Listed | ListFailed: ...

    def renew(
        self, key: str, expected_version: str
    ) -> Renewed | Conflict | Absent | Unsupported | WriteFailed: ...


def encode_token(value: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def decode_token(token: str):
    try:
        return json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid object-store token") from exc


def validate_listing(prefix: str, limit: int) -> None:
    if prefix:
        safe_path(prefix.removesuffix("/"))
    if not 1 <= limit <= 1000:
        raise ValueError("listing limit must be between 1 and 1000")


class LocalStore:
    """SQLite-backed objects with interprocess atomic CAS, not a static web root.

    ``expiry_seconds`` enables an explicit test model: reads/listings hide expired
    rows, and a matching renewal advances their eligibility time. The filesystem
    does NOT delete these rows. With no expiry model, renewal is unsupported.
    Use one expiry policy consistently for every client of a directory.
    """

    def __init__(
        self,
        directory: str | Path,
        *,
        expiry_seconds: float | None = None,
        clock: Callable[[], float] = time.time,
        timeout: float = 30,
    ) -> None:
        if expiry_seconds is not None and expiry_seconds <= 0:
            raise ValueError("expiry_seconds must be positive")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "objects.sqlite3"
        self.expiry_seconds = expiry_seconds
        self.clock = clock
        self.timeout = timeout
        with self._transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS objects (key TEXT PRIMARY KEY, data BLOB NOT NULL, "
                "version TEXT NOT NULL, metadata TEXT NOT NULL, created REAL NOT NULL, expiry REAL)"
            )

    def _connect(self):
        return sqlite3.connect(self.database, timeout=self.timeout)

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _read(self, connection, key: str) -> Present | Absent:
        row = connection.execute(
            "SELECT data, version, metadata, created, expiry FROM objects WHERE key=?", (key,)
        ).fetchone()
        if row is None or (row[4] is not None and row[4] <= self.clock()):
            return Absent()
        return Present(row[0], row[1], json.loads(row[2]), row[3], row[4])

    def read(self, key: str) -> Present | Absent | ReadFailed:
        safe_path(key)
        try:
            with closing(self._connect()) as connection:
                return self._read(connection, key)
        except sqlite3.Error as exc:
            return ReadFailed(str(exc))

    def _put(self, connection, key, data, metadata) -> Present:
        now = self.clock()
        expires = now + self.expiry_seconds if self.expiry_seconds is not None else None
        value = Present(data, str(uuid4()), dict(metadata or {}), now, expires)
        connection.execute(
            "INSERT OR REPLACE INTO objects VALUES (?, ?, ?, ?, ?, ?)",
            (key, data, value.version, json.dumps(value.metadata), now, expires),
        )
        return value

    def write(
        self,
        key: str,
        data: bytes,
        condition: CreateOnly | Match,
        *,
        metadata: Mapping | None = None,
    ) -> Written | Conflict | WriteFailed:
        safe_path(key)
        if not isinstance(condition, (CreateOnly, Match)):
            raise TypeError("write requires CreateOnly or Match")
        try:
            with self._transaction() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = self._read(connection, key)
                if isinstance(condition, CreateOnly):
                    if isinstance(current, Present):
                        return Conflict()
                elif not isinstance(current, Present) or current.version != condition.version:
                    return Conflict()
                value = self._put(connection, key, data, metadata)
            return Written(value.version)
        except sqlite3.Error as exc:
            return WriteFailed(str(exc), outcome_unknown=True)

    def list(
        self, prefix: str = "", *, token: str | None = None, limit: int = 1000
    ) -> Listed | ListFailed:
        validate_listing(prefix, limit)
        after = ""
        if token is not None:
            decoded = decode_token(token)
            if not isinstance(decoded, list) or len(decoded) != 3:
                raise ValueError("invalid listing token")
            directory, original_prefix, after = decoded
            if directory != str(self.directory.resolve()) or original_prefix != prefix:
                raise ValueError("listing token belongs to another query")
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    "SELECT key, version, created, expiry, metadata FROM objects "
                    "WHERE substr(key, 1, ?) = ? AND key > ? "
                    "AND (expiry IS NULL OR expiry > ?) ORDER BY key LIMIT ?",
                    (len(prefix), prefix, after, self.clock(), limit + 1),
                ).fetchall()
            next_token = None
            if len(rows) > limit:
                next_token = encode_token(
                    [str(self.directory.resolve()), prefix, rows[limit - 1][0]]
                )
            return Listed(
                tuple(
                    ObjectInfo(row[0], row[1], row[2], row[3], json.loads(row[4]))
                    for row in rows[:limit]
                ),
                next_token,
            )
        except sqlite3.Error as exc:
            return ListFailed(str(exc))

    def renew(
        self, key: str, expected_version: str
    ) -> Renewed | Conflict | Absent | Unsupported | WriteFailed:
        safe_path(key)
        if self.expiry_seconds is None:
            return Unsupported("LocalStore has no configured expiry model")
        try:
            with self._transaction() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = self._read(connection, key)
                if isinstance(current, Absent):
                    return current
                if current.version != expected_version:
                    return Conflict()
                value = self._put(connection, key, current.data, current.metadata)
            assert value.created_at is not None
            return Renewed(value.version, value.created_at, value.expires_at)
        except sqlite3.Error as exc:
            return WriteFailed(str(exc), outcome_unknown=True)
