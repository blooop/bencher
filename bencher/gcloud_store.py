"""GCS JSON API adapter authenticated by gcloud, with injectable transport.

Structured HTTP statuses avoid depending on gcloud's human-readable diagnostics.
Reads pin generation AND metageneration; versions include both so renewal cannot
silently restore metadata over a concurrent metadata edit. Renewal uploads the
observed bytes again (not a metadata touch), then verifies the new storage age.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from bencher.complete_report import safe_path
from bencher.object_store import (
    Absent,
    Conflict,
    CreateOnly,
    Listed,
    ListFailed,
    Match,
    ObjectInfo,
    Present,
    ReadFailed,
    Renewed,
    Unsupported,
    WriteFailed,
    Written,
    decode_token,
    encode_token,
    validate_listing,
)

# gcloud ships its own interpreter, and an inherited PYTHONPATH puts a foreign
# standard library ahead of its own: gcloud then prints no access token at all,
# which reads as an authentication problem rather than the leaked environment it
# is. Its POSIX wrapper already unsets PYTHONHOME, but nothing guarantees that of
# every entry point, and neither is ever right for a subprocess that is not this
# Python.
_FOREIGN_INTERPRETER_VARS = ("PYTHONPATH", "PYTHONHOME")


def gcloud_env(env: Mapping[str, str]) -> dict[str, str]:
    """Return *env* as the gcloud CLI should see it: without this interpreter's."""
    return {name: value for name, value in env.items() if name not in _FOREIGN_INTERPRETER_VARS}


@dataclass(frozen=True)
class Response:
    status: int
    data: bytes


@dataclass(frozen=True)
class TransportFailed:
    reason: str
    submitted: bool


def request(method, url, data, headers, timeout) -> Response | TransportFailed:
    try:
        with urlopen(
            Request(url, data=data, headers=headers, method=method), timeout=timeout
        ) as out:
            return Response(out.status, out.read())
    except HTTPError as exc:
        return Response(exc.code, exc.read())
    except (OSError, URLError, HTTPException) as exc:
        return TransportFailed(type(exc).__name__, submitted=True)


_SERVING_FIELDS = (
    "contentType",
    "contentEncoding",
    "contentDisposition",
    "contentLanguage",
    "cacheControl",
    "metadata",
    "customTime",
    "storageClass",
)


class GcloudStore:
    """A bucket-scoped object adapter; ``prefix`` confines every operation.

    ``env`` is what gcloud authenticates in, stripped of the variables that
    configure *this* interpreter (see :func:`gcloud_env`); it defaults to the
    process environment. ``expiry_seconds`` describes caller-verified Age-based
    Delete eligibility, not a deletion deadline. This adapter does not
    inspect/change bucket rules. Without that explicit policy renewal is
    unsupported. Multipart uploads hold one object's bytes in memory, consistent
    with the byte-oriented store API.
    """

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        env: Mapping[str, str] | None = None,
        timeout: float = 60,
        transport: Callable = request,
        runner: Callable = subprocess.run,
        token_provider: Callable[[], str] | None = None,
        expiry_seconds: float | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not bucket or any(char in bucket for char in "/?#"):
            raise ValueError("bucket must be a bucket name, not a URL")
        if prefix:
            safe_path(prefix)
        if timeout <= 0 or (expiry_seconds is not None and expiry_seconds <= 0):
            raise ValueError("timeout and configured expiry must be positive")
        self.bucket, self.prefix = bucket, prefix
        self.env = gcloud_env(os.environ if env is None else env)
        self.timeout, self.transport, self.runner = timeout, transport, runner
        self.token_provider = token_provider
        self.expiry_seconds, self.clock = expiry_seconds, clock
        self._token = ""
        self._token_deadline = 0.0

    def _auth(self) -> str | TransportFailed:
        if self.token_provider is not None:
            return self.token_provider()
        if time.monotonic() < self._token_deadline:
            return self._token
        try:
            result = self.runner(
                ["gcloud", "auth", "print-access-token", "--quiet"],
                env=self.env,
                timeout=self.timeout,
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return TransportFailed(f"gcloud authentication: {type(exc).__name__}", submitted=False)
        if result.returncode or not result.stdout.strip():
            return TransportFailed("gcloud authentication failed", submitted=False)
        self._token = result.stdout.strip()
        self._token_deadline = time.monotonic() + 3000
        return self._token

    def _call(self, method, path, *, query=None, data=None, content_type=None, upload=False):
        token = self._auth()
        if isinstance(token, TransportFailed):
            return token
        base = "https://storage.googleapis.com/" + ("upload/" if upload else "") + "storage/v1/"
        url = base + path
        if query:
            url += "?" + urlencode(query)
        headers = {"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"}
        if content_type:
            headers["Content-Type"] = content_type
        return self.transport(method, url, data, headers, self.timeout)

    def _name(self, key: str) -> str:
        safe_path(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def _path(self, key: str) -> str:
        return f"b/{quote(self.bucket, safe='')}/o/{quote(self._name(key), safe='')}"

    def _version(self, key: str, metadata: dict) -> str:
        return encode_token(
            [
                self.bucket,
                self._name(key),
                str(metadata["generation"]),
                str(metadata["metageneration"]),
            ]
        )

    def _condition(self, key: str, condition: CreateOnly | Match) -> dict:
        if isinstance(condition, CreateOnly):
            return {"ifGenerationMatch": "0"}
        if not isinstance(condition, Match):
            raise TypeError("write requires CreateOnly or Match")
        decoded = decode_token(condition.version)
        if (
            not isinstance(decoded, list)
            or len(decoded) != 4
            or decoded[:2] != [self.bucket, self._name(key)]
        ):
            raise ValueError("version token belongs to another object")
        return {"ifGenerationMatch": decoded[2], "ifMetagenerationMatch": decoded[3]}

    def _info(self, key: str, metadata: dict) -> ObjectInfo:
        created = datetime.fromisoformat(metadata["timeCreated"]).timestamp()
        expiry = created + self.expiry_seconds if self.expiry_seconds is not None else None
        serving = {field: metadata[field] for field in _SERVING_FIELDS if field in metadata}
        return ObjectInfo(key, self._version(key, metadata), created, expiry, serving)

    @staticmethod
    def _failure(result: Response | TransportFailed) -> str:
        if isinstance(result, TransportFailed):
            return result.reason
        try:
            message = json.loads(result.data).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            message = ""
        return f"GCS HTTP {result.status}: {str(message)[:1000]}"

    def read(self, key: str) -> Present | Absent | ReadFailed:
        path = self._path(key)
        result = self._call("GET", path)
        if isinstance(result, Response) and result.status == 404:
            return Absent()
        if not isinstance(result, Response) or result.status != 200:
            return ReadFailed(self._failure(result))
        try:
            metadata = json.loads(result.data)
            info = self._info(key, metadata)
            generation, metageneration = (
                str(metadata["generation"]),
                str(metadata["metageneration"]),
            )
            size = int(metadata["size"])
        except (ValueError, KeyError, TypeError) as exc:
            return ReadFailed(f"invalid GCS metadata: {type(exc).__name__}")
        media = self._call(
            "GET",
            path,
            query={
                "alt": "media",
                "generation": generation,
                "ifMetagenerationMatch": metageneration,
            },
        )
        if not isinstance(media, Response) or media.status != 200:
            return ReadFailed(f"generation-pinned download: {self._failure(media)}")
        if len(media.data) != size:
            return ReadFailed("generation-pinned download size mismatch")
        return Present(media.data, info.version, info.metadata, info.created_at, info.expires_at)

    def write(
        self,
        key: str,
        data: bytes,
        condition: CreateOnly | Match,
        *,
        metadata: Mapping | None = None,
    ) -> Written | Conflict | WriteFailed:
        name = self._name(key)
        query = {"uploadType": "multipart", **self._condition(key, condition)}
        if metadata and set(metadata) - set(_SERVING_FIELDS):
            raise ValueError("unsupported GCS serving metadata field")
        media_type = (metadata or {}).get("contentType", "application/octet-stream")
        if "\r" in media_type or "\n" in media_type:
            raise ValueError("invalid media content type")
        boundary = str(uuid4())
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + json.dumps({**(metadata or {}), "name": name}).encode()
            + f"\r\n--{boundary}\r\nContent-Type: {media_type}\r\n\r\n".encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )
        result = self._call(
            "POST",
            f"b/{quote(self.bucket, safe='')}/o",
            query=query,
            data=body,
            content_type=f"multipart/related; boundary={boundary}",
            upload=True,
        )
        if isinstance(result, TransportFailed):
            return WriteFailed(result.reason, outcome_unknown=result.submitted)
        if result.status == 412:
            return Conflict()
        if result.status not in {200, 201}:
            return WriteFailed(self._failure(result), outcome_unknown=result.status >= 500)
        try:
            return Written(self._version(key, json.loads(result.data)))
        except (ValueError, KeyError, TypeError) as exc:
            return WriteFailed(f"invalid GCS write response: {type(exc).__name__}", True)

    def list(
        self, prefix: str = "", *, token: str | None = None, limit: int = 1000
    ) -> Listed | ListFailed:
        validate_listing(prefix, limit)
        remote_prefix = f"{self.prefix}/{prefix}" if self.prefix else prefix
        query = {"prefix": remote_prefix, "maxResults": str(limit)}
        if token:
            decoded = decode_token(token)
            if (
                not isinstance(decoded, list)
                or len(decoded) != 3
                or decoded[:2] != [self.bucket, remote_prefix]
            ):
                raise ValueError("listing token belongs to another query")
            query["pageToken"] = decoded[2]
        result = self._call("GET", f"b/{quote(self.bucket, safe='')}/o", query=query)
        if not isinstance(result, Response) or result.status != 200:
            return ListFailed(self._failure(result))
        try:
            document = json.loads(result.data)
            items = []
            for item in document.get("items", []):
                if not item["name"].startswith(remote_prefix):
                    return ListFailed("GCS returned an object outside the requested prefix")
                key = item["name"][len(self.prefix) + 1 :] if self.prefix else item["name"]
                items.append(self._info(key, item))
            next_token = document.get("nextPageToken")
            if next_token:
                next_token = encode_token([self.bucket, remote_prefix, next_token])
            return Listed(tuple(items), next_token)
        except (ValueError, KeyError, TypeError) as exc:
            return ListFailed(f"invalid GCS listing: {type(exc).__name__}")

    def renew(  # pylint: disable=too-many-return-statements
        self, key: str, expected_version: str
    ) -> Renewed | Conflict | Absent | Unsupported | WriteFailed:
        self._path(key)
        if self.expiry_seconds is None:
            return Unsupported("GCS renewal requires a caller-verified age-based expiry policy")
        current = self.read(key)
        if isinstance(current, Absent):
            return current
        if isinstance(current, ReadFailed):
            return WriteFailed(current.reason, outcome_unknown=False)
        if current.version != expected_version:
            return Conflict()
        started = self.clock()
        outcome = self.write(key, current.data, Match(expected_version), metadata=current.metadata)
        if isinstance(outcome, Conflict):
            return outcome
        if isinstance(outcome, WriteFailed) and not outcome.outcome_unknown:
            return outcome
        verified = self.read(key)
        if not isinstance(verified, Present):
            return WriteFailed("renewal read-back unavailable", outcome_unknown=True)
        if verified.data != current.data or verified.metadata != current.metadata:
            return Conflict()
        if (
            verified.version == expected_version
            or verified.created_at is None
            or current.created_at is None
            or verified.created_at <= current.created_at
            or verified.created_at < started
        ):
            return WriteFailed("renewal has no verified new storage age", outcome_unknown=True)
        return Renewed(verified.version, verified.created_at, verified.expires_at)
