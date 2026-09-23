"""A pointer that is served must not outlive the execution it redirects to."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from bencher.object_store import LocalStore, WriteFailed
from bencher.publication_pointers import PointerCandidate, PointerUnchanged, PointerUpdated
from bencher.publication_renewal import (
    ExecutionRenewed,
    NothingPointedAt,
    PointerMoved,
    RenewalFailed,
    RenewalIncomplete,
    RenewalUnsupported,
    renew_pointed_execution,
)
from bencher.publication_target import (
    PublicationTarget,
    publish_frozen_report,
    renew_pointed_report,
)
from bencher.publishing import CompleteReportPublisher, Published

# The frozen report directory these tests publish, without running a sweep.
pytest_plugins = ["test.test_publishing"]

HTTP_BASE = "https://reports.example.test/bench"
POINTER_KEY = "latest/index.html"
STORAGE_ROOT = "reports"
WINDOW = 100.0


def foreign_candidate(target: str) -> PointerCandidate:
    """A newer candidate of the same ordering policy, from another publication."""
    return PointerCandidate(target, "execution-time-uuid-v1", (2**62, "zzz"))


@pytest.fixture(name="deployment")
def pointed_deployment(report, tmp_path):
    """One published execution, a pointer naming it, and a store that reaps by age."""
    now = [0.0]
    store = LocalStore(tmp_path / "store", expiry_seconds=WINDOW, clock=lambda: now[0])
    publisher = CompleteReportPublisher(store, STORAGE_ROOT, HTTP_BASE, clock=lambda: now[0])
    published = publisher.publish(report)
    assert isinstance(published, Published)
    assert isinstance(publisher.point(published.receipt, POINTER_KEY), PointerUpdated)
    return SimpleNamespace(
        store=store, publisher=publisher, now=now, published=published, report=report
    )


def test_a_pointed_at_report_survives_the_window_that_would_have_reaped_it(deployment):
    """The whole point: the pointer still names bytes the age policy would have taken."""
    deployment.now[0] = WINDOW - 10
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, ExecutionRenewed)
    assert outcome.target == deployment.published.url
    assert outcome.expires_at == WINDOW * 2 - 10
    deployment.now[0] = WINDOW + 10
    # verify returns the manifest it checked, or PublishFailed naming what is gone.
    assert "files" in deployment.publisher.verify(deployment.published.receipt)


def test_without_renewal_the_pointer_serves_a_url_whose_bytes_are_gone(deployment):
    """The failure this exists to prevent, so the test above cannot pass by accident."""
    deployment.now[0] = WINDOW + 10
    assert deployment.store.list().items == ()


def test_every_object_of_the_execution_and_the_pointer_itself_are_renewed(deployment):
    """An execution missing one asset is a broken page, and the redirect expires too."""
    stored = {item.key for item in deployment.store.list().items}
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, ExecutionRenewed)
    assert set(outcome.keys) == stored
    assert POINTER_KEY in outcome.keys
    assert f"{outcome.prefix}/report.json" in outcome.keys


def test_a_store_that_cannot_renew_is_a_deployment_not_a_failure(report, tmp_path):
    """No age policy means nothing is being reaped, so there is nothing to keep alive."""
    store = LocalStore(tmp_path / "store")
    publisher = CompleteReportPublisher(store, STORAGE_ROOT, HTTP_BASE)
    published = publisher.publish(report)
    assert isinstance(published, Published)
    assert isinstance(publisher.point(published.receipt, POINTER_KEY), PointerUpdated)
    outcome = publisher.renew(POINTER_KEY)
    assert isinstance(outcome, RenewalUnsupported)
    assert outcome.target == published.url
    assert not isinstance(outcome, RenewalFailed)


def test_one_refused_object_is_reported_with_the_ones_that_were_renewed(deployment, monkeypatch):
    """A partial renewal is not a smaller success; the report still expires."""
    original = deployment.store.renew
    refused_key = []

    def refuse_one(key, expected_version):
        if key.endswith("summary.json"):
            refused_key.append(key)
            return WriteFailed("backend refused the rewrite", outcome_unknown=False)
        return original(key, expected_version)

    monkeypatch.setattr(deployment.store, "renew", refuse_one)
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, RenewalIncomplete)
    assert [item.key for item in outcome.refused] == refused_key
    assert outcome.refused[0].reason == "backend refused the rewrite"
    assert f"{outcome.prefix}/report.json" in outcome.renewed
    assert POINTER_KEY in outcome.renewed


def test_a_pointer_that_names_nothing_asks_nothing_of_the_caller(tmp_path):
    """Before the first publication there is no current execution to keep alive."""
    store = LocalStore(tmp_path / "store", expiry_seconds=WINDOW)
    outcome = renew_pointed_execution(store, POINTER_KEY, STORAGE_ROOT, HTTP_BASE)
    assert isinstance(outcome, NothingPointedAt)


def test_a_conflicting_version_is_reread_and_renewed_at_the_one_it_now_has(deployment, monkeypatch):
    """A version observed at listing time is stale the moment anything else writes."""
    original = deployment.store.renew
    conflicts = []

    def conflict_once(key, expected_version):
        if key.endswith("index.html") and not conflicts:
            conflicts.append(key)
            current = deployment.store.read(key)
            original(key, current.version)
            return original(key, expected_version)
        return original(key, expected_version)

    monkeypatch.setattr(deployment.store, "renew", conflict_once)
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, ExecutionRenewed)
    assert conflicts


def test_an_object_that_never_stops_conflicting_is_refused_not_retried_forever(
    deployment, monkeypatch
):
    from bencher.object_store import Conflict

    original = deployment.store.renew
    attempts = []

    def always_conflict(key, expected_version):
        if key.endswith("summary.json"):
            attempts.append(key)
            return Conflict()
        return original(key, expected_version)

    monkeypatch.setattr(deployment.store, "renew", always_conflict)
    outcome = deployment.publisher.renew(POINTER_KEY, attempts=2)
    assert isinstance(outcome, RenewalIncomplete)
    assert len(attempts) == 2
    assert "conflict" in outcome.refused[0].reason


def test_a_publication_that_moves_the_pointer_mid_renewal_is_reported_as_such(
    deployment, monkeypatch
):
    """The execution just renewed is no longer current, and the new one is newer still."""
    from bencher.publication_pointers import update_pointer

    original = deployment.store.renew
    moved = []

    def move_pointer_once(key, expected_version):
        if not moved:
            moved.append(key)
            other = f"{HTTP_BASE}/{uuid4()}/index.html"
            update_pointer(deployment.store, POINTER_KEY, foreign_candidate(other))
        return original(key, expected_version)

    monkeypatch.setattr(deployment.store, "renew", move_pointer_once)
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, PointerMoved)
    assert outcome.renewed == deployment.published.url
    assert outcome.current != outcome.renewed


def test_an_execution_whose_manifest_is_gone_is_already_broken(deployment):
    """Renewing what is left of a reaped execution would report a healthy report."""
    from bencher.publication_pointers import update_pointer

    other = f"{HTTP_BASE}/{uuid4()}/index.html"
    assert isinstance(
        update_pointer(deployment.store, POINTER_KEY, foreign_candidate(other)), PointerUpdated
    )
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, RenewalFailed)
    assert "manifest" in outcome.reason


@pytest.mark.parametrize(
    "target",
    [
        "https://elsewhere.test/x/index.html",
        f"{HTTP_BASE}/../elsewhere/index.html",
        f"{HTTP_BASE}/",
    ],
)
def test_a_target_served_from_somewhere_else_is_not_this_deployments_to_renew(deployment, target):
    """Storage and serving are independent namespaces, related only by the two roots."""
    from bencher.publication_pointers import update_pointer

    update_pointer(deployment.store, POINTER_KEY, foreign_candidate(target))
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, RenewalFailed)
    assert "not served from here" in outcome.reason


def test_a_pointer_object_that_is_not_a_pointer_fails_closed(deployment):
    from bencher.object_store import Match, Present

    current = deployment.store.read(POINTER_KEY)
    assert isinstance(current, Present)
    deployment.store.write(POINTER_KEY, b"<html>an old alias</html>", Match(current.version))
    outcome = deployment.publisher.renew(POINTER_KEY)
    assert isinstance(outcome, RenewalFailed)
    assert "invalid pointer" in outcome.reason


@pytest.mark.parametrize("attempts", [0, -1])
def test_a_nonpositive_retry_budget_is_a_programming_error(deployment, attempts):
    with pytest.raises(ValueError, match="attempts"):
        deployment.publisher.renew(POINTER_KEY, attempts=attempts)


def test_publication_renews_the_execution_its_pointer_now_names(report, tmp_path):
    """A republished older execution keeps its committed bytes and its old age."""
    target = PublicationTarget(
        store=str(tmp_path / "store"),
        prefix=STORAGE_ROOT,
        http_base=HTTP_BASE,
        pointer=POINTER_KEY,
        expiry_days=1,
    )
    outcome = publish_frozen_report(report, target)
    assert isinstance(outcome, Published)
    assert isinstance(outcome.pointer, PointerUpdated)
    assert isinstance(outcome.renewal, ExecutionRenewed)
    assert outcome.renewal.target == outcome.url


def test_a_pointer_that_did_not_move_made_nothing_newly_current(report, tmp_path):
    target = PublicationTarget(
        store=str(tmp_path / "store"),
        prefix=STORAGE_ROOT,
        http_base=HTTP_BASE,
        pointer=POINTER_KEY,
        expiry_days=1,
    )
    assert isinstance(publish_frozen_report(report, target), Published)
    again = publish_frozen_report(report, target)
    assert isinstance(again, Published)
    assert isinstance(again.pointer, PointerUnchanged)
    assert again.renewal is None


def test_a_refused_renewal_is_never_a_failed_publication(report, tmp_path, monkeypatch):
    """The report is committed and immutable long before anything is renewed."""
    target = PublicationTarget(
        store=str(tmp_path / "store"),
        prefix=STORAGE_ROOT,
        http_base=HTTP_BASE,
        pointer=POINTER_KEY,
        expiry_days=1,
    )
    publisher = target.publisher()
    monkeypatch.setattr(publisher, "renew", lambda *_args, **_kwargs: RenewalFailed("no"))
    outcome = publish_frozen_report(report, target, publisher)
    assert isinstance(outcome, Published)
    assert outcome.url.startswith(HTTP_BASE)
    assert isinstance(outcome.renewal, RenewalFailed)


def test_a_target_without_a_pointer_has_no_execution_to_keep_alive(tmp_path):
    target = PublicationTarget(store=str(tmp_path / "store"), prefix="reports", http_base=HTTP_BASE)
    with pytest.raises(ValueError, match="no pointer"):
        renew_pointed_report(target)
