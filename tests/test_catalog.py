from pathlib import Path

import pytest

from ru_ai_channels.catalog import (
    Catalog,
    CatalogError,
    Channel,
    Chat,
    Section,
    Stat,
    load_catalog,
    load_stats,
    save_stats,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = [Section("s", "Раздел", "Описание")]


def catalog(*channels: Channel, chats: tuple[Chat, ...] = ()) -> Catalog:
    return Catalog(SECTIONS, list(channels), list(chats))


def test_real_data_file_is_valid_and_in_target_size() -> None:
    loaded = load_catalog(ROOT / "data" / "channels.toml")

    assert 40 <= len(loaded.channels) <= 60


def test_validate_rejects_duplicate_handles_ignoring_case() -> None:
    with pytest.raises(CatalogError, match="Дубликат"):
        validate(catalog(Channel("Abcde", "A", "s", "x"), Channel("abcde", "B", "s", "y")))


def test_validate_rejects_unknown_section() -> None:
    with pytest.raises(CatalogError, match="раздел"):
        validate(catalog(Channel("abcde", "A", "nope", "x")))


def test_validate_rejects_handle_with_at_sign() -> None:
    with pytest.raises(CatalogError, match="хэндл"):
        validate(catalog(Channel("@abcde", "A", "s", "x")))


def test_real_data_file_has_chats() -> None:
    loaded = load_catalog(ROOT / "data" / "channels.toml")

    assert any(c.handle == "privatekey_ai_chat" for c in loaded.chats)


def test_validate_rejects_chat_with_same_handle_as_channel() -> None:
    with pytest.raises(CatalogError, match="Дубликат"):
        validate(catalog(Channel("abcde", "A", "s", "x"), chats=(Chat("ABCDE", "B", "y"),)))


def test_validate_rejects_chat_with_multiline_about() -> None:
    with pytest.raises(CatalogError, match="about"):
        validate(catalog(chats=(Chat("abcde", "B", "a\nb"),)))


def test_stats_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    stats = {"abcde": Stat(10, "2026-11-12T10:00:00+00:00", "2026-11-12")}

    save_stats(path, stats, "2026-11-12")

    assert load_stats(path) == stats


def test_load_stats_of_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_stats(tmp_path / "none.json") == {}
