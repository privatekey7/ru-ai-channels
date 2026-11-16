"""Файл данных каталога (data/channels.toml) и кэш статистики (data/stats.json)."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

HANDLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


class CatalogError(ValueError):
    """Файл данных нарушает формат."""


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class Channel:
    handle: str
    name: str
    section: str
    about: str


@dataclass(frozen=True)
class Chat:
    """Открытый чат или группа: отдельный раздел, без даты последнего поста."""

    handle: str
    name: str
    about: str


@dataclass(frozen=True)
class Stat:
    """Последние известные данные о канале."""

    subscribers: int | None = None
    last_post: str | None = None  # ISO 8601
    checked: str | None = None  # дата последней успешной проверки, YYYY-MM-DD
    feed_open: bool = True


@dataclass(frozen=True)
class Catalog:
    sections: list[Section]
    channels: list[Channel]
    chats: list[Chat] = field(default_factory=list)


def load_catalog(path: Path) -> Catalog:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    sections = [Section(**s) for s in data.get("section", [])]
    channels = [Channel(**c) for c in data.get("channel", [])]
    chats = [Chat(**c) for c in data.get("chat", [])]
    catalog = Catalog(sections, channels, chats)
    validate(catalog)
    return catalog


def validate(catalog: Catalog) -> None:
    section_ids = {s.id for s in catalog.sections}
    seen: set[str] = set()
    entries: list[Channel | Chat] = [*catalog.channels, *catalog.chats]
    for entry in entries:
        if not HANDLE_RE.match(entry.handle):
            raise CatalogError(f"Некорректный хэндл: {entry.handle!r} (без @, 5-32 символа)")
        key = entry.handle.lower()
        if key in seen:
            raise CatalogError(f"Дубликат канала или чата: {entry.handle}")
        seen.add(key)
        if not entry.about.strip() or "\n" in entry.about:
            raise CatalogError(f"{entry.handle}: 'about' должна быть одной непустой строкой")
    for ch in catalog.channels:
        if ch.section not in section_ids:
            raise CatalogError(f"{ch.handle}: неизвестный раздел {ch.section!r}")


def load_stats(path: Path) -> dict[str, Stat]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {h.lower(): Stat(**s) for h, s in raw.get("channels", {}).items()}


def save_stats(path: Path, stats: dict[str, Stat], updated: str) -> None:
    payload = {
        "updated": updated,
        "channels": {h: asdict(s) for h, s in sorted(stats.items())},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_updated(path: Path) -> str | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("updated")
    return value if isinstance(value, str) else None
