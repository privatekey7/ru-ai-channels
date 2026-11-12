from pathlib import Path

import httpx
import pytest

from ru_ai_channels import cli

FIXTURES = Path(__file__).parent / "fixtures"
DATA = """
[[section]]
id = "s"
title = "Раздел"
description = "Описание"

[[channel]]
handle = "test_channel"
name = "Тест"
section = "s"
about = "Проверка"

[[channel]]
handle = "other_channel"
name = "Другой"
section = "s"
about = "Ещё проверка"
"""
TEMPLATE = "{{COUNT}}|{{STALE}}|{{UPDATED}}\n{{SECTIONS}}\n"


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "channels.toml").write_text(DATA, encoding="utf-8")
    (tmp_path / "tmpl.md").write_text(TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(cli, "CHANNELS", tmp_path / "channels.toml")
    monkeypatch.setattr(cli, "STATS", tmp_path / "stats.json")
    monkeypatch.setattr(cli, "TEMPLATE", tmp_path / "tmpl.md")
    monkeypatch.setattr(cli, "README", tmp_path / "README.md")
    return tmp_path


def use_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(cli, "make_client", lambda: httpx.Client(transport=handler))


def test_update_writes_stats_and_readme(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    html = (FIXTURES / "feed_open.html").read_text(encoding="utf-8")
    use_transport(monkeypatch, httpx.MockTransport(lambda _: httpx.Response(200, text=html)))
    monkeypatch.setattr("ru_ai_channels.fetch.time.sleep", lambda _: None)

    code = cli.main(["update", "--delay", "0"])

    readme = (workdir / "README.md").read_text(encoding="utf-8")
    assert code == 0
    assert "96 400" in readme
    assert (workdir / "stats.json").exists()


def test_update_fails_and_keeps_data_when_every_request_fails(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transport(monkeypatch, httpx.MockTransport(lambda _: httpx.Response(403)))

    code = cli.main(["update", "--delay", "0"])

    assert code == 1
    assert not (workdir / "stats.json").exists()
    assert not (workdir / "README.md").exists()


def test_check_detects_stale_readme_and_render_fixes_it(workdir: Path) -> None:
    (workdir / "README.md").write_text("старое", encoding="utf-8")

    assert cli.main(["check"]) == 1
    assert cli.main(["render"]) == 0
    assert cli.main(["check"]) == 0
