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
