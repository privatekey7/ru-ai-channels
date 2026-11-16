from datetime import date
from pathlib import Path

from ru_ai_channels.catalog import (
    Catalog,
    Channel,
    Chat,
    Section,
    Stat,
    load_catalog,
    load_stats,
    load_updated,
)
from ru_ai_channels.render import (
    format_last_post,
    format_number,
    is_stale,
    render_chats,
    render_readme,
    render_section,
)

TODAY = date(2026, 11, 12)
SECTION = Section("cc", "Claude Code", "Описание раздела")
CHANNELS = [
    Channel("small_ch", "Малый", "cc", "О малом"),
    Channel("big_ch", "Большой | канал", "cc", "О большом"),
    Channel("no_data", "Без данных", "cc", "Нет цифр"),
    Channel("old_one", "Старый", "cc", "Давно молчит"),
]
STATS = {
    "small_ch": Stat(1_550, "2026-11-11T10:00:00+00:00", "2026-11-12"),
    "big_ch": Stat(96_400, "2026-11-12T10:00:00+00:00", "2026-11-12"),
    "old_one": Stat(5_000, "2026-09-01T10:00:00+00:00", "2026-11-12"),
}


def test_format_number_uses_non_breaking_space_as_thousands_separator() -> None:
    assert format_number(96_400) == "96 400"
    assert format_number(None) == "—"


def test_section_is_sorted_by_subscribers_and_unknown_goes_last() -> None:
    text = render_section(SECTION, CHANNELS, STATS, TODAY)

    positions = [text.index(f"t.me/{h})") for h in ("big_ch", "old_one", "small_ch", "no_data")]
    assert positions == sorted(positions)


def test_section_header_counts_channels() -> None:
    assert "### Claude Code (4)" in render_section(SECTION, CHANNELS, STATS, TODAY)


def test_pipe_in_name_is_escaped_so_table_does_not_break() -> None:
    text = render_section(SECTION, CHANNELS, STATS, TODAY)

    assert r"[Большой \| канал](https://t.me/big_ch)" in text


def test_channel_without_posts_for_30_days_is_marked() -> None:
    stat = STATS["old_one"]

    assert is_stale(stat, TODAY)
    assert format_last_post(stat, TODAY) == "⏸ 01.09.2026 (72 дн. назад)"


def test_fresh_channel_is_not_marked() -> None:
    stat = STATS["small_ch"]

    assert not is_stale(stat, TODAY)
    assert format_last_post(stat, TODAY) == "11.11.2026"


def test_exactly_30_days_counts_as_stale() -> None:
    stat = Stat(1, "2026-10-13T10:00:00+00:00", "2026-11-12")

    assert is_stale(stat, TODAY)


def test_closed_feed_is_shown_explicitly() -> None:
    stat = Stat(4, None, "2026-11-12", feed_open=False)

    assert format_last_post(stat, TODAY) == "лента закрыта"


CHATS = [
    Chat("small_chat", "Малый | чат", "Помогают с настройкой"),
    Chat("big_chat", "Большой чат", "Обсуждение"),
]
CHAT_STATS = {
    "small_chat": Stat(62, None, "2026-11-12", feed_open=False),
    "big_chat": Stat(2_688, None, "2026-11-12", feed_open=False),
}


def test_chats_are_sorted_by_members_and_show_member_count() -> None:
    text = render_chats(CHATS, CHAT_STATS)

    assert "### Чаты (2)" in text
    assert "| Участники |" in text
    assert text.index("t.me/big_chat)") < text.index("t.me/small_chat)")
    assert r"[Малый \| чат](https://t.me/small_chat) | Помогают с настройкой | 62 |" in text


def test_no_chats_render_nothing() -> None:
    assert render_chats([], {}) == ""


def test_chats_do_not_count_as_channels_or_stale() -> None:
    template = "{{COUNT}}/{{STALE}}/{{CHAT_COUNT}}\n{{CHATS}}"
    catalog = Catalog([SECTION], CHANNELS, CHATS)

    text = render_readme(template, catalog, STATS | CHAT_STATS, TODAY, "2026-11-12")

    assert text.startswith("4/1/2\n### Чаты (2)")


def test_readme_fills_all_placeholders_and_skips_empty_sections() -> None:
    template = "Каналов: {{COUNT}}, молчат: {{STALE}}, обновлено {{UPDATED}}\n\n{{SECTIONS}}\n"
    catalog = Catalog([SECTION, Section("empty", "Пустой", "-")], CHANNELS)

    text = render_readme(template, catalog, STATS, TODAY, "2026-11-12")

    assert text.startswith("Каналов: 4, молчат: 1, обновлено 2026-11-12")
    assert "{{" not in text
    assert "Пустой" not in text


def test_readme_is_deterministic() -> None:
    template = "{{SECTIONS}}{{COUNT}}{{STALE}}{{UPDATED}}"
    catalog = Catalog([SECTION], CHANNELS)

    first = render_readme(template, catalog, STATS, TODAY, "2026-11-12")

    assert first == render_readme(template, catalog, STATS, TODAY, "2026-11-12")


def test_committed_readme_matches_data() -> None:
    root = Path(__file__).resolve().parents[1]
    stats_path = root / "data" / "stats.json"
    updated = load_updated(stats_path)
    # «Молчащие» считаются на дату обновления данных, а не по часам, поэтому проверка стабильна.
    today = date.fromisoformat(updated) if updated else TODAY
    template = (root / "templates" / "README.md.tmpl").read_text(encoding="utf-8")

    expected = render_readme(
        template,
        load_catalog(root / "data" / "channels.toml"),
        load_stats(stats_path),
        today,
        updated,
    )

    assert (root / "README.md").read_text(encoding="utf-8") == expected
