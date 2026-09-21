"""Machine-readable GCS outcomes; no gcloud diagnostic-string interpretation."""

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from bencher.gcloud_store import GcloudStore, Response, TransportFailed
from bencher.object_store import (
    Absent,
    Conflict,
    CreateOnly,
    Listed,
    ListFailed,
    Match,
    Present,
    ReadFailed,
    Renewed,
    WriteFailed,
    Written,
)

pytest_plugins = ["test.test_publishing"]


def metadata(generation="1", created="2026-09-13T00:00:00Z"):
    return {
        "name": "sandbox/key",
        "generation": generation,
        "metageneration": "2",
        "timeCreated": created,
        "size": "3",
        "contentType": "text/html",
        "cacheControl": "no-cache",
        "metadata": {"custom": "preserved"},
    }


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, data, headers, timeout):
        self.calls.append((method, url, data, headers, timeout))
        return self.responses.pop(0)


def response(value):
    return Response(200, json.dumps(value).encode())


def store_with(*responses):
    transport = FakeTransport(*responses)
    store = GcloudStore(
        "bucket",
        prefix="sandbox",
        transport=transport,
        token_provider=lambda: "test-token",
        expiry_seconds=90,
        clock=lambda: 1789257660.0,
    )
    return store, transport


def test_read_pins_bytes_to_generation_and_metadata_version():
    store, transport = store_with(response(metadata()), Response(200, b"abc"))
    value = store.read("key")
    assert isinstance(value, Present) and value.data == b"abc"
    query = parse_qs(urlsplit(transport.calls[1][1]).query)
    assert query == {"alt": ["media"], "generation": ["1"], "ifMetagenerationMatch": ["2"]}
    assert value.metadata["metadata"] == {"custom": "preserved"}
    assert value.created_at and value.expires_at == value.created_at + 90


@pytest.mark.parametrize("status,expected", [(404, Absent), (403, ReadFailed), (500, ReadFailed)])
def test_read_statuses_are_distinct(status, expected):
    store, _ = store_with(Response(status, b"{}"))
    assert isinstance(store.read("key"), expected)


def test_pinned_generation_disappearing_is_failed_read_not_empty_baseline():
    store, _ = store_with(response(metadata()), Response(404, b"{}"))
    assert isinstance(store.read("key"), ReadFailed)


@pytest.mark.parametrize(
    "status,expected", [(412, Conflict), (403, WriteFailed), (500, WriteFailed)]
)
def test_write_statuses_are_distinct(status, expected):
    store, transport = store_with(Response(status, b"{}"))
    outcome = store.write("key", b"abc", CreateOnly())
    assert isinstance(outcome, expected)
    assert parse_qs(urlsplit(transport.calls[0][1]).query)["ifGenerationMatch"] == ["0"]
    if isinstance(outcome, WriteFailed):
        assert outcome.outcome_unknown == (status == 500)


def test_conditional_write_uses_both_generation_and_metageneration():
    store, transport = store_with(
        response(metadata()), Response(200, b"abc"), response(metadata("2"))
    )
    current = store.read("key")
    assert isinstance(current, Present)
    assert isinstance(store.write("key", b"new", Match(current.version)), Written)
    query = parse_qs(urlsplit(transport.calls[-1][1]).query)
    assert query["ifGenerationMatch"] == ["1"] and query["ifMetagenerationMatch"] == ["2"]


def test_multipart_media_content_type_matches_metadata():
    store, transport = store_with(response(metadata()))
    store.write("key", b"abc", CreateOnly(), metadata={"contentType": "text/html"})
    assert b"Content-Type: text/html\r\n\r\nabc" in transport.calls[0][2]


def test_timeout_after_submission_is_explicitly_unknown():
    store, _ = store_with(TransportFailed("timeout", submitted=True))
    result = store.write("key", b"abc", CreateOnly())
    assert isinstance(result, WriteFailed) and result.outcome_unknown


def test_gcloud_auth_timeout_is_not_a_submitted_write():
    def runner(command, **kwargs):
        assert kwargs["env"] == {"CLOUDSDK_CONFIG": "/isolated"}
        assert kwargs["timeout"] == 7
        raise subprocess.TimeoutExpired(command, 7)

    store = GcloudStore("bucket", env={"CLOUDSDK_CONFIG": "/isolated"}, timeout=7, runner=runner)
    result = store.write("key", b"abc", CreateOnly())
    assert isinstance(result, WriteFailed) and not result.outcome_unknown


def test_gcloud_never_authenticates_under_a_foreign_interpreter():
    """gcloud runs its own Python, so an inherited PYTHONPATH makes it import a
    standard library that is not its own -- reported as a failed token, not as the
    leaked environment it is."""
    seen = {}

    def runner(_command, **kwargs):
        seen.update(kwargs["env"])
        raise OSError("gcloud not run")

    store = GcloudStore(
        "bucket",
        env={
            "PYTHONPATH": "/opt/other/site-packages",
            "PYTHONHOME": "/opt/other",
            "CLOUDSDK_CONFIG": "/isolated",
        },
        runner=runner,
    )
    store.write("key", b"abc", CreateOnly())
    assert seen == {"CLOUDSDK_CONFIG": "/isolated"}


def test_the_default_environment_is_stripped_too(monkeypatch):
    """The default is the process environment, which is where these leak from."""
    monkeypatch.setenv("PYTHONPATH", "/opt/other/site-packages")
    monkeypatch.setenv("BENCHER_TEST_MARKER", "kept")
    seen = {}

    def runner(_command, **kwargs):
        seen.update(kwargs["env"])
        raise OSError("gcloud not run")

    GcloudStore("bucket", runner=runner).write("key", b"abc", CreateOnly())
    assert "PYTHONPATH" not in seen
    assert seen["BENCHER_TEST_MARKER"] == "kept"


def test_listing_preserves_server_continuation_even_on_empty_page():
    store, transport = store_with(
        response({"nextPageToken": "server-token"}), response({"items": [metadata()]})
    )
    first = store.list(limit=1)
    assert isinstance(first, Listed) and not first.complete and not first.items
    second = store.list(token=first.next_token, limit=1)
    assert isinstance(second, Listed) and second.complete and second.items[0].key == "key"
    assert parse_qs(urlsplit(transport.calls[-1][1]).query)["pageToken"] == ["server-token"]


def test_denied_listing_is_not_empty():
    store, _ = store_with(Response(403, b"{}"))
    assert isinstance(store.list(), ListFailed)


@pytest.mark.parametrize("lost_ack", [False, True])
def test_renewal_rewrites_same_bytes_and_verifies_new_creation_time(lost_ack):
    old = metadata()
    new = metadata("2", "2026-09-13T00:01:00Z")
    store, transport = store_with(
        response(old),
        Response(200, b"abc"),
        response(old),
        Response(200, b"abc"),
        TransportFailed("timeout", submitted=True) if lost_ack else response(new),
        response(new),
        Response(200, b"abc"),
    )
    current = store.read("key")
    assert isinstance(current, Present)
    renewed = store.renew("key", current.version)
    assert isinstance(renewed, Renewed)
    assert renewed.version != current.version and renewed.created_at > current.created_at
    assert b'"custom": "preserved"' in transport.calls[4][2]
    assert b"abc" in transport.calls[4][2]


def test_equal_bytes_without_new_age_do_not_prove_renewal():
    old = metadata()
    store, _ = store_with(
        response(old),
        Response(200, b"abc"),
        response(old),
        Response(200, b"abc"),
        TransportFailed("timeout", submitted=True),
        response(old),
        Response(200, b"abc"),
    )
    current = store.read("key")
    assert isinstance(current, Present)
    outcome = store.renew("key", current.version)
    assert isinstance(outcome, WriteFailed) and outcome.outcome_unknown


def test_renewal_conflict_never_replays_stale_bytes():
    store, transport = store_with(
        response(metadata()), Response(200, b"abc"), response(metadata("2")), Response(200, b"new")
    )
    old = store.read("key")
    assert isinstance(old, Present)
    assert isinstance(store.renew("key", old.version), Conflict)
    assert all(call[0] == "GET" for call in transport.calls)


@pytest.mark.skipif(not os.environ.get("BENCHER_GCS_CONTRACT_ROOT"), reason="explicit GCS opt-in")
def test_gcloud_live_disposable_contract(report):
    """Small real objects only, under a fresh prefix; bucket lifecycle retires them."""
    root = urlsplit(os.environ["BENCHER_GCS_CONTRACT_ROOT"])
    assert root.scheme == "gs" and root.netloc and root.path.strip("/")
    prefix = f"{root.path.strip('/')}/{uuid4()}"
    store = GcloudStore(root.netloc, prefix=prefix, expiry_seconds=7 * 86400)
    print(f"disposable contract prefix: gs://{root.netloc}/{prefix}")
    assert isinstance(store.read("key"), Absent)
    serving = {
        "contentType": "text/html",
        "cacheControl": "no-cache",
        "contentDisposition": "inline",
        "metadata": {"contract": "bencher-B2"},
    }
    initial = store.write("key", b"abc", CreateOnly(), metadata=serving)
    assert isinstance(initial, Written), initial
    current = store.read("key")
    assert isinstance(current, Present), current
    assert current.data == b"abc" and current.version == initial.version
    assert all(current.metadata.get(key) == value for key, value in serving.items())
    assert isinstance(store.write("key", b"wrong", CreateOnly()), Conflict)
    newer = store.write("key", b"new", Match(initial.version), metadata=serving)
    assert isinstance(newer, Written), newer
    assert isinstance(store.write("key", b"stale", Match(initial.version)), Conflict)
    before = store.read("key")
    assert isinstance(before, Present)
    renewed = store.renew("key", before.version)
    assert isinstance(renewed, Renewed), renewed
    after = store.read("key")
    assert isinstance(after, Present)
    assert after.data == before.data and after.metadata == before.metadata
    assert after.created_at is not None and before.created_at is not None
    assert after.expires_at is not None and before.expires_at is not None
    assert after.created_at > before.created_at
    assert after.expires_at > before.expires_at
    assert isinstance(store.renew("key", before.version), Conflict)
    with ThreadPoolExecutor(4) as pool:
        race = list(
            pool.map(lambda i: store.write("race", str(i).encode(), CreateOnly()), range(4))
        )
    assert sum(isinstance(item, Written) for item in race) == 1
    assert sum(isinstance(item, Conflict) for item in race) == 3
    first = store.list(limit=1)
    assert isinstance(first, Listed) and not first.complete, first
    second = store.list(token=first.next_token, limit=1)
    assert isinstance(second, Listed) and second.complete, second
    assert {item.key for page in [first, second] for item in page.items} == {"key", "race"}
    from bencher.publication_pointers import PointerUpdated
    from bencher.publishing import CompleteReportPublisher, Published

    publisher = CompleteReportPublisher(
        store, "reports", "https://example.test/contract", minimum_remaining_seconds=86400
    )
    published = publisher.publish(report)
    assert isinstance(published, Published), published
    assert publisher.publish(report) == published
    assert isinstance(publisher.point(published.receipt, "latest/index.html"), PointerUpdated)
    print(
        json.dumps(
            {
                "before_created": before.created_at,
                "after_created": after.created_at,
                "same_bytes": before.data == after.data,
                "same_serving_metadata": before.metadata == after.metadata,
                "race_winners": 1,
                "listing_pages": 2,
            }
        )
    )
