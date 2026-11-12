"""Сборка README из шаблона, файла данных и статистики."""

from __future__ import annotations

from datetime import date, datetime

from .catalog import Catalog, Channel, Section, Stat

STALE_DAYS = 30


def format_number(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}".replace(",", " ")


def days_since(last_post: str | None, today: date) -> int | None:
    if not last_post:
        return None
    return (today - datetime.fromisoformat(last_post).date()).days


def is_stale(stat: Stat | None, today: date) -> bool:
    days = days_since(stat.last_post if stat else None, today)
    return days is not None and days >= STALE_DAYS


def format_last_post(stat: Stat | None, today: date) -> str:
    if stat is None or stat.checked is None:
        return "—"
    if stat.last_post is None:
        return "лента закрыта" if not stat.feed_open else "—"
    posted = datetime.fromisoformat(stat.last_post).date()
    text = posted.strftime("%d.%m.%Y")
    days = (today - posted).days
    return f"⏸ {text} ({days} дн. назад)" if days >= STALE_DAYS else text


def _escape(text: str) -> str:
    return text.replace("|", r"\|")


def _sort_key(channel: Channel, stats: dict[str, Stat]) -> tuple[int, str]:
    stat = stats.get(channel.handle.lower())
    subs = stat.subscribers if stat and stat.subscribers is not None else -1
    return (-subs, channel.handle.lower())


def render_section(
    section: Section, channels: list[Channel], stats: dict[str, Stat], today: date
) -> str:
    own = sorted(
        (c for c in channels if c.section == section.id), key=lambda c: _sort_key(c, stats)
    )
    lines = [f"### {section.title} ({len(own)})", "", section.description, ""]
    lines += [
        "| Канал | О чём | Подписчики | Последний пост |",
        "|---|---|---:|---|",
    ]
    for ch in own:
        stat = stats.get(ch.handle.lower())
        subs = format_number(stat.subscribers if stat else None)
        lines.append(
            f"| [{_escape(ch.name)}](https://t.me/{ch.handle}) "
            f"| {_escape(ch.about)} | {subs} | {format_last_post(stat, today)} |"
        )
    return "\n".join(lines)


def render_readme(
    template: str,
    catalog: Catalog,
    stats: dict[str, Stat],
    today: date,
    updated: str | None,
) -> str:
    sections = [
        render_section(s, catalog.channels, stats, today)
        for s in catalog.sections
        if any(c.section == s.id for c in catalog.channels)
    ]
    stale = sum(is_stale(stats.get(c.handle.lower()), today) for c in catalog.channels)
    return (
        template.replace("{{COUNT}}", str(len(catalog.channels)))
        .replace("{{STALE}}", str(stale))
        .replace("{{UPDATED}}", updated or "ещё не обновлялось")
        .replace("{{SECTIONS}}", "\n\n".join(sections))
    )
