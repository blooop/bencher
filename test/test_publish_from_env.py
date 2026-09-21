"""Publishing a run's own report, configured from outside the process that runs it."""

from __future__ import annotations

import json
import tempfile

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.object_store import LocalStore, Present
from bencher.publication_target import (
    HTTP_BASE_ENV,
    PREFIX_ENV,
    RECEIPT_ENV,
    STORE_ENV,
    PublicationFailed,
    PublicationTarget,
)
from bencher.publishing import PublishFailed

HTTP_BASE = "https://reports.example.test/bench"


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
        PublicationTarget(
            store="/store", prefix="reports", http_base=HTTP_BASE, **{field: value}
        )


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
