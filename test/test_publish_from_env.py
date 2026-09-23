"""Publishing a run's own report, configured from outside the process that runs it."""

from __future__ import annotations

import json
import shutil
import tempfile
from types import SimpleNamespace
from uuid import uuid4

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.object_store import Absent, LocalStore, Present
from bencher.publication_pointers import (
    PointerFailed,
    PointerUnchanged,
    PointerUpdated,
    read_pointer,
)
from bencher.publication_target import (
    HTTP_BASE_ENV,
    POINTER_ENV,
    PREFIX_ENV,
    RECEIPT_ENV,
    STORE_ENV,
    PublicationFailed,
    PublicationTarget,
    commit_frozen_report,
    publish_frozen_report,
)
from bencher.publishing import (
    CompleteReportPublisher,
    PublicationReceipt,
    Published,
    PublishFailed,
)

# The frozen report directory every pointer test publishes, without a sweep.
pytest_plugins = ["test.test_publishing"]

HTTP_BASE = "https://reports.example.test/bench"
POINTER_KEY = "latest/index.html"


def benchmark(run_cfg=None):
    bench = bn.Bench("published", ExampleBenchCfg(), run_cfg=run_cfg)
    bench.collect(input_vars=["theta"], result_vars=["out_sin"])
    bench.close()
    return bench


@pytest.fixture(name="staging")
def staging_root(tmp_path, monkeypatch):
    """Where an unasked-for freeze would land. `tempfile.tempdir` rather than
    TMPDIR: `gettempdir` caches its answer, so the variable is read once per
    process and a later export is ignored."""
    root = tmp_path / "tmp"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return root


@pytest.fixture(name="configured")
def configured_publication(tmp_path, monkeypatch) -> None:
    """What a CI job exports around the process that runs the benchmark."""
    monkeypatch.setenv(STORE_ENV, str(tmp_path / "store"))
    monkeypatch.setenv(PREFIX_ENV, "reports/nightly")
    monkeypatch.setenv(HTTP_BASE_ENV, HTTP_BASE)
    monkeypatch.setenv(RECEIPT_ENV, str(tmp_path / "receipt.json"))


def test_publication_is_off_unless_it_is_configured():
    assert PublicationTarget.from_env({}) is None
    assert PublicationTarget.from_env({"OTHER": "x"}) is None


def test_a_half_configured_target_is_refused_by_name():
    """Publishing to a store nothing serves would produce bytes no one can name,
    and silently skipping would hide the typo until someone wanted the report."""
    with pytest.raises(ValueError, match=HTTP_BASE_ENV):
        PublicationTarget.from_env({STORE_ENV: "gs://bucket", PREFIX_ENV: "reports"})


def test_lifetimes_are_read_as_days():
    target = PublicationTarget.from_env(
        {
            STORE_ENV: "gs://bucket/root",
            PREFIX_ENV: "reports",
            HTTP_BASE_ENV: HTTP_BASE,
            "BENCHER_PUBLISH_EXPIRY_DAYS": "30",
            "BENCHER_PUBLISH_MINIMUM_REMAINING_DAYS": "7",
        }
    )
    assert target.expiry_days == 30
    assert target.minimum_remaining_days == 7
    assert target.publisher().minimum_remaining_seconds == 7 * 86400


@pytest.mark.parametrize("value", ["soon", "-1"])
def test_a_lifetime_that_is_not_days_is_refused(value):
    with pytest.raises(ValueError, match="BENCHER_PUBLISH_EXPIRY_DAYS"):
        PublicationTarget.from_env(
            {
                STORE_ENV: "gs://bucket",
                PREFIX_ENV: "reports",
                HTTP_BASE_ENV: HTTP_BASE,
                "BENCHER_PUBLISH_EXPIRY_DAYS": value,
            }
        )


@pytest.mark.usefixtures("configured")
def test_a_run_publishes_the_report_it_froze(tmp_path, monkeypatch):
    """The whole point: the launcher exported an environment, and a URL came back."""
    monkeypatch.chdir(tmp_path)
    with bn.execution_context(source_revision="launcher-sha") as execution:
        bn.run(benchmark, show=False, report_directory=str(tmp_path / "out"))
    receipt = json.loads((tmp_path / "receipt.json").read_text())
    assert receipt["url"] == f"{HTTP_BASE}/{execution.uuid}/index.html"
    assert receipt["execution"]["source_revision"] == "launcher-sha"
    store = LocalStore(str(tmp_path / "store"))
    committed = store.read(f"reports/nightly/{execution.uuid}/report.json")
    assert isinstance(committed, Present)
    assert json.loads(committed.data)["execution"]["uuid"] == execution.uuid
    assert isinstance(store.read(f"reports/nightly/{execution.uuid}/index.html"), Present)
    assert bn.verify_report(tmp_path / "out" / execution.uuid)["entry_page"] == "index.html"


@pytest.mark.usefixtures("configured")
def test_publishing_needs_no_report_directory(staging, tmp_path, monkeypatch):
    """A staging freeze is not an artifact anyone asked to keep, so it does not
    survive its own publication."""
    monkeypatch.chdir(tmp_path)
    with bn.execution_context() as execution:
        bn.run(benchmark, show=False)
    assert json.loads((tmp_path / "receipt.json").read_text())["url"].endswith(
        f"/{execution.uuid}/index.html"
    )
    store = LocalStore(str(tmp_path / "store"))
    assert isinstance(store.read(f"reports/nightly/{execution.uuid}/index.html"), Present)
    assert list(staging.iterdir()) == []


@pytest.mark.usefixtures("configured")
def test_a_failed_publication_keeps_what_it_could_not_commit(staging, tmp_path, monkeypatch):
    """The render is cheap; the measurements behind it are not. A store that
    refuses the write is exactly when the frozen bytes matter, and the error
    names the directory `bencher publish` can be pointed at."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "bencher.publication_target.publish_frozen_report",
        lambda directory, target, publisher=None: PublishFailed("store refused the write"),
    )
    with pytest.raises(PublicationFailed) as failure:
        bn.run(benchmark, show=False)
    kept = [path for path in staging.iterdir() if path.is_dir()]
    assert len(kept) == 1
    frozen = next(path for path in kept[0].iterdir() if path.is_dir())
    assert str(frozen) in str(failure.value)
    assert bn.verify_report(frozen)["schema_version"] == 1


def test_an_argument_publishes_without_any_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = PublicationTarget(
        store=str(tmp_path / "store"),
        prefix="reports",
        http_base=HTTP_BASE,
        receipt=tmp_path / "receipt.json",
    )
    runner = bn.BenchRunner("explicit", run_cfg=bn.BenchRunCfg())
    runner.add(benchmark)
    runner.run(show=False, publication=target)
    assert runner.publication.url.startswith(f"{HTTP_BASE}/")
    assert json.loads((tmp_path / "receipt.json").read_text())["url"] == runner.publication.url


def test_an_unconfigured_run_freezes_nothing(tmp_path, monkeypatch):
    """Publication is the only thing that makes a complete report unasked for."""
    monkeypatch.chdir(tmp_path)
    runner = bn.BenchRunner("plain", run_cfg=bn.BenchRunCfg())
    runner.add(benchmark)
    runner.run(show=False)
    assert runner.publication is None


@pytest.mark.usefixtures("configured", "staging")
def test_a_later_run_does_not_report_the_previous_run_s_receipt(tmp_path, monkeypatch):
    """A reused runner publishing nothing must not still name the last URL."""
    monkeypatch.chdir(tmp_path)
    runner = bn.BenchRunner("reused", run_cfg=bn.BenchRunCfg())
    runner.add(benchmark)
    runner.run(show=False)
    assert runner.publication is not None
    for name in (STORE_ENV, PREFIX_ENV, HTTP_BASE_ENV, RECEIPT_ENV):
        monkeypatch.delenv(name)
    runner.run(show=False)
    assert runner.publication is None


@pytest.mark.usefixtures("configured")
def test_a_target_no_publisher_accepts_is_refused_before_the_sweep(staging, tmp_path, monkeypatch):
    """A prefix the key layout rejects costs the whole run and leaves a frozen
    report nothing names, so the target is built before any measurement is."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(PREFIX_ENV, "../escape")
    runner = bn.BenchRunner("rejected", run_cfg=bn.BenchRunCfg())
    runner.add(benchmark)
    with pytest.raises(ValueError, match="unsafe inventory path"):
        runner.run(show=False)
    assert runner.results == []
    assert list(staging.iterdir()) == []


@pytest.mark.parametrize(
    "field, value",
    [
        ("expiry_days", float("nan")),
        ("expiry_days", float("inf")),
        ("expiry_days", 0),
        ("expiry_days", -1),
        ("minimum_remaining_days", float("nan")),
        ("minimum_remaining_days", float("inf")),
        ("minimum_remaining_days", -1),
    ],
)
def test_a_lifetime_the_stores_cannot_honour_is_refused_at_construction(field, value):
    """`nan` is neither positive nor negative, so every `<= 0` guard downstream
    waves it through and the lifetime a publication requires is never checked."""
    with pytest.raises(ValueError, match=field):
        PublicationTarget(store="/store", prefix="reports", http_base=HTTP_BASE, **{field: value})


@pytest.mark.parametrize("field", ["store", "prefix", "http_base"])
def test_an_empty_location_is_refused_at_construction(field):
    """An empty store is the working directory, which is nobody's object store."""
    fields = {"store": "/store", "prefix": "reports", "http_base": HTTP_BASE, field: ""}
    with pytest.raises(ValueError, match=field):
        PublicationTarget(**fields)


def test_the_cli_refuses_a_lifetime_it_cannot_honour(tmp_path, capsys):
    """argparse takes `nan` as a float; nothing downstream rejects it."""
    from bencher.publishing_cli import main

    code = main(
        [
            str(tmp_path / "frozen"),
            "--store",
            str(tmp_path / "store"),
            "--prefix",
            "reports",
            "--http-base",
            HTTP_BASE,
            "--expiry-days",
            "nan",
        ]
    )
    assert code == 1
    assert "expiry_days" in capsys.readouterr().err
    assert not (tmp_path / "store").exists()


@pytest.mark.usefixtures("configured")
def test_a_failed_publication_leaves_an_asked_for_report_directory_alone(tmp_path, monkeypatch):
    """A directory the launcher asked to keep is not staging, so the failure
    names where the report already is rather than moving or removing it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "bencher.publication_target.publish_frozen_report",
        lambda directory, target, publisher=None: PublishFailed("store refused the write"),
    )
    with pytest.raises(PublicationFailed) as failure:
        bn.run(benchmark, show=False, report_directory=str(tmp_path / "out"))
    frozen = next(path for path in (tmp_path / "out").iterdir() if path.is_dir())
    assert str(frozen) in str(failure.value)
    assert bn.verify_report(frozen)["schema_version"] == 1


def test_an_unpublished_url_is_never_written_to_the_receipt(tmp_path):
    """The receipt names a URL as served; a refused publication has none."""
    receipt = tmp_path / "receipt.json"
    target = PublicationTarget(
        store=str(tmp_path / "store"),
        prefix="reports",
        http_base=HTTP_BASE,
        receipt=receipt,
    )
    refusing = SimpleNamespace(publish=lambda directory: PublishFailed("store refused the write"))
    assert isinstance(publish_frozen_report(tmp_path, target, refusing), PublishFailed)
    assert not receipt.exists()


def test_a_receipt_that_cannot_be_written_still_names_the_published_url(tmp_path):
    """The bytes are committed and immutable by the time the receipt is written,
    so a failure there must not take the URL down with it: the run is not
    repeatable, and nothing else in the process has seen it."""
    url = f"{HTTP_BASE}/0123/index.html"
    receipt = PublicationReceipt(
        prefix="reports/0123", url=url, manifest_sha256="0" * 64, execution={}, results=()
    )
    occupied = tmp_path / "receipt.json"
    occupied.mkdir()
    target = PublicationTarget(
        store=str(tmp_path / "store"), prefix="reports", http_base=HTTP_BASE, receipt=occupied
    )
    publisher = SimpleNamespace(publish=lambda directory: Published(url=url, receipt=receipt))
    with pytest.raises(OSError, match=url):
        publish_frozen_report(tmp_path, target, publisher)


def pointed(tmp_path, pointer: str | None = POINTER_KEY, **overrides) -> PublicationTarget:
    return PublicationTarget(
        store=str(tmp_path / "store"),
        prefix="reports",
        http_base=HTTP_BASE,
        pointer=pointer,
        **overrides,
    )


def reexecuted(source, destination, executed_at: str):
    """Copy a frozen report as if a different execution had produced it."""
    shutil.copytree(source, destination)
    manifest = json.loads((destination / "report.json").read_text())
    manifest["execution"]["uuid"] = str(uuid4())
    manifest["execution"]["executed_at"] = executed_at
    (destination / "report.json").write_text(json.dumps(manifest))
    return destination


def test_a_pointer_is_absent_unless_the_environment_names_one():
    """An exported-but-empty variable is an unset one, as it is for the receipt."""
    base = {STORE_ENV: "/store", PREFIX_ENV: "reports", HTTP_BASE_ENV: HTTP_BASE}
    assert PublicationTarget.from_env(base).pointer is None
    assert PublicationTarget.from_env({**base, POINTER_ENV: ""}).pointer is None
    assert PublicationTarget.from_env({**base, POINTER_ENV: POINTER_KEY}).pointer == POINTER_KEY


def test_a_pointer_set_to_nothing_is_not_the_same_as_no_pointer():
    """The caller asked for a pointer, and no store holds an object named "".
    Reading it as "no pointer" would serve a stale redirect forever and say
    nothing, which is the failure this whole feature exists to prevent."""
    with pytest.raises(ValueError, match="pointer"):
        PublicationTarget(store="/store", prefix="reports", http_base=HTTP_BASE, pointer="")


def test_a_pointer_key_the_store_would_refuse_is_refused_before_the_sweep():
    """The update runs after every measurement, so the key is checked with the
    rest of the target, where a typo costs nothing."""
    with pytest.raises(ValueError, match="unsafe inventory path"):
        PublicationTarget(
            store="/store", prefix="reports", http_base=HTTP_BASE, pointer="../escape"
        )


def test_a_publication_with_no_pointer_writes_none(report, tmp_path):
    outcome = publish_frozen_report(report, pointed(tmp_path, pointer=None))
    assert isinstance(outcome, Published)
    assert outcome.pointer is None
    assert isinstance(LocalStore(str(tmp_path / "store")).read(POINTER_KEY), Absent)


def test_a_configured_pointer_names_the_report_that_was_just_published(report, tmp_path):
    outcome = publish_frozen_report(report, pointed(tmp_path))
    assert isinstance(outcome, Published)
    assert isinstance(outcome.pointer, PointerUpdated)
    current = LocalStore(str(tmp_path / "store")).read(POINTER_KEY)
    assert isinstance(current, Present)
    assert read_pointer(current.data).target == outcome.url


def test_republishing_an_older_execution_leaves_the_pointer_alone(report, tmp_path):
    """Ranking is by measurement time, not upload time, so replaying an old
    execution publishes its own immutable URL and moves nothing."""
    target = pointed(tmp_path)
    newest = publish_frozen_report(report, target)
    older = reexecuted(report, tmp_path / "older", "2020-01-01T00:00:00+00:00")
    outcome = publish_frozen_report(older, target)
    assert isinstance(outcome, Published)
    assert isinstance(outcome.pointer, PointerUnchanged)
    assert outcome.url != newest.url
    current = LocalStore(str(tmp_path / "store")).read(POINTER_KEY)
    assert read_pointer(current.data).target == newest.url


def test_a_refused_pointer_does_not_unpublish_the_report(report, tmp_path, monkeypatch):
    """The bytes are committed before the pointer moves. Reporting a failure
    here would send a caller off to run a sweep whose report is already served."""
    monkeypatch.setattr(
        CompleteReportPublisher, "point", lambda *args, **kwargs: PointerFailed("denied")
    )
    receipt = tmp_path / "receipt.json"
    outcome = commit_frozen_report(report, pointed(tmp_path, receipt=receipt))
    assert isinstance(outcome, Published)
    assert outcome.pointer == PointerFailed("denied")
    assert json.loads(receipt.read_text())["url"] == outcome.url


@pytest.mark.usefixtures("configured")
def test_a_run_points_at_the_report_it_froze(tmp_path, monkeypatch):
    """The asymmetry this closes: the CLI could move a pointer and a run could not."""
    monkeypatch.setenv(POINTER_ENV, POINTER_KEY)
    monkeypatch.chdir(tmp_path)
    runner = bn.BenchRunner("pointed", run_cfg=bn.BenchRunCfg())
    runner.add(benchmark)
    runner.run(show=False)
    assert isinstance(runner.publication.pointer, PointerUpdated)
    current = LocalStore(str(tmp_path / "store")).read(POINTER_KEY)
    assert isinstance(current, Present)
    assert read_pointer(current.data).target == runner.publication.url


@pytest.mark.usefixtures("configured")
def test_a_run_keeps_its_url_when_the_pointer_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(POINTER_ENV, POINTER_KEY)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        CompleteReportPublisher, "point", lambda *args, **kwargs: PointerFailed("denied")
    )
    runner = bn.BenchRunner("pointed", run_cfg=bn.BenchRunCfg())
    runner.add(benchmark)
    runner.run(show=False)
    assert runner.publication.url.startswith(f"{HTTP_BASE}/")
    assert runner.publication.pointer == PointerFailed("denied")
    assert json.loads((tmp_path / "receipt.json").read_text())["url"] == runner.publication.url
