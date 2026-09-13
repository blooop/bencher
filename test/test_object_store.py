"""Backend-neutral conditional object operations, including real process races."""

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

import pytest

from bencher.object_store import (
    Absent,
    Conflict,
    CreateOnly,
    Listed,
    LocalStore,
    Match,
    Present,
    Renewed,
    Unsupported,
    Written,
)


def _create_once(directory, value):
    return LocalStore(directory).write("race", value, CreateOnly())


def test_local_conditional_operations(tmp_path):
    store = LocalStore(tmp_path)
    assert isinstance(store.read("a"), Absent)
    first = store.write("a", b"first", CreateOnly(), metadata={"contentType": "text/html"})
    assert isinstance(first, Written)
    assert isinstance(store.write("a", b"wrong", CreateOnly()), Conflict)
    read = store.read("a")
    assert isinstance(read, Present)
    assert (read.data, read.version, read.metadata) == (
        b"first",
        first.version,
        {"contentType": "text/html"},
    )
    second = store.write("a", b"second", Match(first.version))
    assert isinstance(second, Written)
    assert second.version != first.version
    assert isinstance(store.write("a", b"stale", Match(first.version)), Conflict)
    assert isinstance(store.write("missing", b"stale", Match(first.version)), Conflict)
    assert isinstance(store.renew("a", second.version), Unsupported)


def test_local_create_is_atomic_across_processes(tmp_path):
    LocalStore(tmp_path)
    with ProcessPoolExecutor(4, mp_context=get_context("spawn")) as pool:
        outcomes = list(pool.map(_create_once, [tmp_path] * 12, [bytes([i]) for i in range(12)]))
    assert sum(isinstance(item, Written) for item in outcomes) == 1
    assert sum(isinstance(item, Conflict) for item in outcomes) == 11


def test_local_pagination_is_bounded_and_resumable(tmp_path):
    store = LocalStore(tmp_path)
    for key in ["a/1", "a/2", "a/3", "b/1"]:
        store.write(key, key.encode(), CreateOnly())
    first = store.list("a/", limit=2)
    assert isinstance(first, Listed)
    assert [item.key for item in first.items] == ["a/1", "a/2"]
    assert not first.complete and first.next_token
    second = LocalStore(tmp_path).list("a/", token=first.next_token, limit=2)
    assert isinstance(second, Listed)
    assert [item.key for item in second.items] == ["a/3"]
    assert second.complete and second.next_token is None
    with pytest.raises(ValueError, match="token"):
        store.list("b/", token=first.next_token)


def test_local_expiry_is_explicit_and_renewal_preserves_content(tmp_path):
    now = [0.0]
    store = LocalStore(tmp_path, expiry_seconds=90, clock=lambda: now[0])
    first = store.write("a", b"original", CreateOnly(), metadata={"cacheControl": "no-cache"})
    assert isinstance(first, Written)
    now[0] = 60
    renewed = store.renew("a", first.version)
    assert isinstance(renewed, Renewed)
    assert renewed.created_at == 60 and renewed.expires_at == 150
    assert renewed.version != first.version
    assert isinstance(store.renew("a", first.version), Conflict)
    current = store.read("a")
    assert isinstance(current, Present)
    assert current.data == b"original" and current.metadata == {"cacheControl": "no-cache"}
    now[0] = 100
    assert isinstance(store.read("a"), Present)
    now[0] = 151
    assert isinstance(store.read("a"), Absent)
    assert isinstance(store.renew("a", renewed.version), Absent)
    assert store.list().items == ()
    # The fake clock hides expired entries; no filesystem lifecycle is implied.
    assert (tmp_path / "objects.sqlite3").exists()
    assert isinstance(store.write("a", b"new", CreateOnly()), Written)


@pytest.mark.parametrize("key", ["", "/a", "../a", "a/../b", "a//b", "a\\b", "a\x00b"])
def test_local_rejects_unsafe_keys(tmp_path, key):
    with pytest.raises(ValueError):
        LocalStore(tmp_path).read(key)
