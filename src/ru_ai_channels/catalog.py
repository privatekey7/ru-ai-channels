"""Файл данных каталога (data/channels.toml) и кэш статистики (data/stats.json)."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass
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


def load_catalog(path: Path) -> Catalog:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    sections = [Section(**s) for s in data.get("section", [])]
    channels = [Channel(**c) for c in data.get("channel", [])]
    validate(Catalog(sections, channels))
    return Catalog(sections, channels)


def validate(catalog: Catalog) -> None:
    section_ids = {s.id for s in catalog.sections}
    seen: set[str] = set()
    for ch in catalog.channels:
        if not HANDLE_RE.match(ch.handle):
            raise CatalogError(f"Некорректный хэндл: {ch.handle!r} (без @, 5-32 символа)")
        key = ch.handle.lower()
        if key in seen:
            raise CatalogError(f"Дубликат канала: {ch.handle}")
        seen.add(key)
        if ch.section not in section_ids:
            raise CatalogError(f"{ch.handle}: неизвестный раздел {ch.section!r}")
        if not ch.about.strip() or "\n" in ch.about:
            raise CatalogError(f"{ch.handle}: 'about' должна быть одной непустой строкой")


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
