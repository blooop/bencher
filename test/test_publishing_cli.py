"""Publish command dispatch leaves legacy rendering/compare arguments intact."""

import json

from bencher.render import main

pytest_plugins = ["test.test_publishing"]


def test_publish_cli_prints_and_persists_receipt(report, tmp_path, capsys):
    receipt = tmp_path / "receipts" / "published.json"
    args = [
        "publish",
        str(report),
        "--store",
        str(tmp_path / "store"),
        "--prefix",
        "reports",
        "--http-base",
        "https://example.test/bench",
        "--receipt",
        str(receipt),
        "--pointer",
        "latest/index.html",
    ]
    assert main(args) == 0
    initial = json.loads(capsys.readouterr().out)
    assert json.loads(receipt.read_text()) == initial
    assert initial["url"].startswith("https://example.test/bench/")
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == initial


def test_publish_cli_failure_is_nonzero_and_visible(tmp_path, capsys):
    assert (
        main(
            [
                "publish",
                str(tmp_path / "missing"),
                "--store",
                str(tmp_path / "store"),
                "--prefix",
                "reports",
                "--http-base",
                "https://example.test",
            ]
        )
        == 1
    )
    assert "invalid frozen report" in capsys.readouterr().err


def test_receipt_survives_failed_pointer_update(report, tmp_path, capsys, monkeypatch):
    from bencher.publication_pointers import PointerFailed
    from bencher.publishing import CompleteReportPublisher

    monkeypatch.setattr(
        CompleteReportPublisher, "point", lambda *args, **kwargs: PointerFailed("denied")
    )
    receipt = tmp_path / "receipt.json"
    assert (
        main(
            [
                "publish",
                str(report),
                "--store",
                str(tmp_path / "store"),
                "--prefix",
                "reports",
                "--http-base",
                "https://example.test",
                "--receipt",
                str(receipt),
                "--pointer",
                "latest",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert json.loads(receipt.read_text()) == json.loads(output.out)
    assert "report committed, pointer update failed: denied" in output.err


def test_renew_cli_keeps_the_pointed_at_report_alive(report, tmp_path, capsys):
    store = str(tmp_path / "store")
    published = [
        "publish",
        str(report),
        "--store",
        store,
        "--prefix",
        "reports",
        "--http-base",
        "https://example.test/bench",
        "--pointer",
        "latest/index.html",
        "--expiry-days",
        "7",
    ]
    assert main(published) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "renew",
                "--store",
                store,
                "--prefix",
                "reports",
                "--http-base",
                "https://example.test/bench",
                "--pointer",
                "latest/index.html",
                "--expiry-days",
                "7",
            ]
        )
        == 0
    )
    assert "renewed 5 objects of https://example.test/bench/" in capsys.readouterr().out


def test_renew_cli_says_when_nothing_is_pointed_at(tmp_path, capsys):
    assert (
        main(
            [
                "renew",
                "--store",
                str(tmp_path / "store"),
                "--prefix",
                "reports",
                "--http-base",
                "https://example.test/bench",
                "--pointer",
                "latest/index.html",
                "--expiry-days",
                "7",
            ]
        )
        == 0
    )
    assert "nothing renewed: no pointer is published" in capsys.readouterr().out


def test_renew_cli_is_nonzero_when_a_lifetime_was_not_extended(tmp_path, capsys):
    from bencher.object_store import CreateOnly, LocalStore

    store = LocalStore(tmp_path / "store", expiry_seconds=7 * 86400)
    store.write("latest/index.html", b"<html>an old alias</html>", CreateOnly())
    assert (
        main(
            [
                "renew",
                "--store",
                str(tmp_path / "store"),
                "--prefix",
                "reports",
                "--http-base",
                "https://example.test/bench",
                "--pointer",
                "latest/index.html",
                "--expiry-days",
                "7",
            ]
        )
        == 1
    )
    assert "renew failed: invalid pointer" in capsys.readouterr().err
