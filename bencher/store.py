"""A key-value store wrapper around minimalkv with pickle serialization, tag tracking, and size limits.

Replaces diskcache.Cache with a backend-agnostic store that supports local filesystem
and remote backends (GCS, S3, etc.) via minimalkv.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import re
import hashlib
import tempfile

from minimalkv.fs import FilesystemStore

logger = logging.getLogger(__name__)

_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
_MAX_KEY_LEN = 200
_TAG_META_KEY = "__bencher_tags__"


def _sanitize_key(key: str) -> str:
    """Ensure key is safe for all minimalkv backends."""
    if _SAFE_KEY_RE.match(key) and len(key) <= _MAX_KEY_LEN:
        return key
    return hashlib.sha256(key.encode()).hexdigest()


class BencherStore:
    """Dict-like cache wrapping a minimalkv backend with pickle serialization,
    tag tracking, and size-limited eviction."""

    def __init__(
        self,
        directory: str = "",
        size_limit: int = 0,
        tag_index: bool = False,
        backend=None,
    ):
        self._directory = directory
        self._size_limit = size_limit
        self._tag_index = tag_index

        if backend is not None:
            self._store = backend
        else:
            os.makedirs(directory, exist_ok=True)
            self._store = FilesystemStore(directory)

        # Tag state
        self._tags: dict[str, list[str]] = {}
        self._key_to_tag: dict[str, str] = {}
        if self._tag_index:
            self._load_tags()

    # -- Dict-like API --

    def __getitem__(self, key: str):
        safe = _sanitize_key(key)
        try:
            data = self._store.get(safe)
        except KeyError:
            raise KeyError(key) from None
        return pickle.loads(data)  # noqa: S301

    def __setitem__(self, key: str, value):
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        safe = _sanitize_key(key)
        try:
            self._store.get(safe)
            return True
        except KeyError:
            return False

    def __delitem__(self, key: str):
        self.delete(key)

    # -- Explicit API --

    def set(self, key: str, value, tag: str | None = None) -> None:
        """Store a value, optionally associating it with a tag."""
        safe = _sanitize_key(key)
        data = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        self._store.put(safe, data)
        if tag is not None and self._tag_index:
            self._add_tag(safe, tag)
        self._enforce_size_limit()

    def get(self, key: str, default=None):
        """Get a value, returning default if not found."""
        try:
            return self[key]
        except KeyError:
            return default

    def delete(self, key: str) -> None:
        """Delete a key from the store."""
        safe = _sanitize_key(key)
        try:
            self._store.delete(safe)
        except KeyError:
            pass
        if self._tag_index:
            self._remove_key_from_tags(safe)

    def clear(self) -> None:
        """Delete all entries from the store."""
        for key in list(self._store.keys()):
            if key == _TAG_META_KEY:
                continue
            try:
                self._store.delete(key)
            except KeyError:
                pass
        if self._tag_index:
            self._tags = {}
            self._key_to_tag = {}
            self._save_tags()

    def evict(self, tag: str) -> int:
        """Remove all entries associated with a tag. Returns count of removed items."""
        if not self._tag_index:
            return 0
        keys = self._tags.pop(tag, [])
        count = 0
        for key in keys:
            try:
                self._store.delete(key)
                count += 1
            except KeyError:
                pass
            self._key_to_tag.pop(key, None)
        self._save_tags()
        return count

    def volume(self) -> int:
        """Return total size of stored data in bytes."""
        if not self._directory or not os.path.isdir(self._directory):
            return 0
        total = 0
        for entry in os.scandir(self._directory):
            if entry.is_file():
                total += entry.stat().st_size
        return total

    @property
    def directory(self) -> str:
        """Return the store directory path."""
        return self._directory

    # -- Lifecycle --

    def close(self) -> None:
        """Close the store (no-op for filesystem)."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Tag internals --

    def _tags_file(self) -> str:
        return os.path.join(self._directory, "_tags.json")

    def _load_tags(self) -> None:
        path = self._tags_file()
        if os.path.exists(path):
            with open(path) as f:
                self._tags = json.load(f)
            self._key_to_tag = {}
            for tag, keys in self._tags.items():
                for key in keys:
                    self._key_to_tag[key] = tag
        else:
            self._tags = {}
            self._key_to_tag = {}

    def _save_tags(self) -> None:
        path = self._tags_file()
        # Atomic write via temp file + rename
        fd, tmp = tempfile.mkstemp(dir=self._directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._tags, f)
            os.replace(tmp, path)
        except BaseException:
            with open(os.devnull):
                pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _add_tag(self, safe_key: str, tag: str) -> None:
        # Remove from old tag if re-tagged
        old_tag = self._key_to_tag.get(safe_key)
        if old_tag is not None and old_tag != tag and old_tag in self._tags:
            self._tags[old_tag] = [k for k in self._tags[old_tag] if k != safe_key]
            if not self._tags[old_tag]:
                del self._tags[old_tag]

        if tag not in self._tags:
            self._tags[tag] = []
        if safe_key not in self._tags[tag]:
            self._tags[tag].append(safe_key)
        self._key_to_tag[safe_key] = tag
        self._save_tags()

    def _remove_key_from_tags(self, safe_key: str) -> None:
        tag = self._key_to_tag.pop(safe_key, None)
        if tag is not None and tag in self._tags:
            self._tags[tag] = [k for k in self._tags[tag] if k != safe_key]
            if not self._tags[tag]:
                del self._tags[tag]
            self._save_tags()

    # -- Size limit enforcement --

    def _enforce_size_limit(self) -> None:
        if self._size_limit <= 0 or not self._directory:
            return
        current = self.volume()
        if current <= self._size_limit:
            return
        target = int(self._size_limit * 0.9)
        # Collect data files sorted by mtime (oldest first)
        entries = []
        for entry in os.scandir(self._directory):
            if entry.is_file() and not entry.name.startswith("_"):
                stat = entry.stat()
                entries.append((entry.name, stat.st_mtime, stat.st_size))
        entries.sort(key=lambda e: e[1])
        for name, _, size in entries:
            if current <= target:
                break
            try:
                self._store.delete(name)
                if self._tag_index:
                    self._remove_key_from_tags(name)
                current -= size
            except KeyError:
                pass
