"""One authoritative redirect object, with ordering reevaluated after each CAS race."""

from bencher.object_store import Conflict, LocalStore, Present, WriteFailed
from bencher.publication_pointers import (
    PointerCandidate,
    PointerFailed,
    PointerUnchanged,
    PointerUpdated,
    read_pointer,
    update_pointer,
)


def candidate(rank, target=None, eligible=True):
    return PointerCandidate(
        target or f"https://reports.example/{rank}/index.html",
        "revision-attempt-v1",
        (rank, 1),
        eligible=eligible,
    )


def test_older_revision_rerun_cannot_regress_deployment(tmp_path):
    store = LocalStore(tmp_path)
    assert isinstance(update_pointer(store, "latest/index.html", candidate(10)), PointerUpdated)
    old_rerun = PointerCandidate(
        "https://reports.example/old-rerun/index.html", "revision-attempt-v1", (9, 100)
    )
    assert isinstance(update_pointer(store, "latest/index.html", old_rerun), PointerUnchanged)
    current = store.read("latest/index.html")
    assert isinstance(current, Present)
    assert read_pointer(current.data) == candidate(10)
    assert b"url=https://reports.example/10/index.html" in current.data


def test_ineligible_candidate_never_reads_or_writes(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    monkeypatch.setattr(store, "read", lambda key: (_ for _ in ()).throw(AssertionError(key)))
    assert isinstance(
        update_pointer(store, "latest", candidate(11, eligible=False)), PointerUnchanged
    )


def test_newer_writer_during_render_is_not_overwritten(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    original = store.write
    raced = []

    def competing(key, data, condition, **kwargs):
        if not raced:
            raced.append(True)
            other = LocalStore(tmp_path)
            assert isinstance(update_pointer(other, key, candidate(20)), PointerUpdated)
        return original(key, data, condition, **kwargs)

    monkeypatch.setattr(store, "write", competing)
    result = update_pointer(store, "latest", candidate(10))
    assert isinstance(result, PointerUnchanged) and result.target == candidate(20).target
    assert read_pointer(store.read("latest").data) == candidate(20)


def test_conflict_rereads_and_retries_newer_candidate(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    original = store.write
    writes = []

    def conflict_once(key, data, condition, **kwargs):
        writes.append(key)
        return Conflict() if len(writes) == 1 else original(key, data, condition, **kwargs)

    monkeypatch.setattr(store, "write", conflict_once)
    assert isinstance(update_pointer(store, "latest", candidate(10)), PointerUpdated)
    assert len(writes) == 2


def test_cas_retry_budget_is_bounded(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    writes = []

    def always_conflict(key, *_args, **_kwargs):
        writes.append(key)
        return Conflict()

    monkeypatch.setattr(store, "write", always_conflict)
    result = update_pointer(store, "latest", candidate(10), attempts=3)
    assert isinstance(result, PointerFailed) and len(writes) == 3


def test_lost_ack_resolves_without_rewriting(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    original = store.write
    writes = []

    def lose_ack(key, data, condition, **kwargs):
        writes.append(key)
        original(key, data, condition, **kwargs)
        return WriteFailed("timeout", outcome_unknown=True)

    monkeypatch.setattr(store, "write", lose_ack)
    assert isinstance(update_pointer(store, "latest", candidate(10)), PointerUnchanged)
    assert len(writes) == 1


def test_different_ordering_policy_and_equal_rank_conflict_are_visible(tmp_path):
    store = LocalStore(tmp_path)
    update_pointer(store, "latest", candidate(10))
    assert isinstance(
        update_pointer(store, "latest", candidate(10, "https://elsewhere.test")), PointerFailed
    )
    other_policy = PointerCandidate("https://example.test", "another-policy", (11, 1))
    assert isinstance(update_pointer(store, "latest", other_policy), PointerFailed)


def test_target_lifetime_guard_runs_before_committing_new_reference(tmp_path):
    store = LocalStore(tmp_path)
    result = update_pointer(
        store, "latest", candidate(10), verify_target=lambda: "dependency lifetime is unverified"
    )
    assert isinstance(result, PointerFailed)
    assert store.list().items == ()
