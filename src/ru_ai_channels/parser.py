"""Разбор страницы https://t.me/s/<канал>: подписчики, название, дата последнего поста."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from html import unescape


class PageKind(StrEnum):
    """Что отдал Telegram по адресу канала."""

    FEED = "feed"  # открытая лента t.me/s/<канал>
    CLOSED = "closed"  # канал есть, но превью ленты отключено
    NOT_FOUND = "not_found"  # такого канала нет или это не канал


@dataclass(frozen=True)
class ChannelInfo:
    kind: PageKind
    title: str | None = None
    subscribers: int | None = None
    last_post: datetime | None = None


_COUNTER = re.compile(
    r'<span class="counter_value">([^<]+)</span>\s*<span class="counter_type">([^<]+)</span>'
)
_TITLE = re.compile(r'tgme_channel_info_header_title"[^>]*>\s*<span[^>]*>(.*?)</span>', re.S)
_DATE = re.compile(r'class="tgme_widget_message_date"[^>]*>\s*<time datetime="([^"]+)"')
_PAGE_TITLE = re.compile(r'class="tgme_page_title"[^>]*>\s*<span[^>]*>(.*?)</span>', re.S)
_PAGE_EXTRA = re.compile(r'class="tgme_page_extra">\s*([^<]*?)\s*<', re.S)
_TAGS = re.compile(r"<[^>]+>")


def parse_count(raw: str) -> int | None:
    """'920' -> 920, '96.4K' -> 96400, '1 020' -> 1020, '1.2M' -> 1200000."""
    text = raw.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([KkMm]?)", text)
    if not match:
        return None
    number, suffix = float(match.group(1)), match.group(2).upper()
    factor = {"": 1, "K": 1_000, "M": 1_000_000}[suffix]
    return round(number * factor)


def _clean(fragment: str) -> str:
    return unescape(_TAGS.sub("", fragment)).strip()


def parse_channel_page(html: str) -> ChannelInfo:
    """Разобрать HTML страницы t.me/s/<канал> (или t.me/<канал>, если лента закрыта)."""
    if "tgme_channel_info" in html:
        return _parse_feed(html)
    if "tgme_page_title" in html:
        return _parse_card(html)
    return ChannelInfo(kind=PageKind.NOT_FOUND)


def _parse_feed(html: str) -> ChannelInfo:
    title_match = _TITLE.search(html)
    subscribers = None
    for value, label in _COUNTER.findall(html):
        if label.strip().lower().startswith("subscriber"):
            subscribers = parse_count(value)
            break
    dates = [datetime.fromisoformat(d) for d in _DATE.findall(html)]
    return ChannelInfo(
        kind=PageKind.FEED,
        title=_clean(title_match.group(1)) if title_match else None,
        subscribers=subscribers,
        last_post=max(dates) if dates else None,
    )


def _parse_card(html: str) -> ChannelInfo:
    """Карточка t.me/<канал>: подписчики есть, ленты нет (или это пользователь/бот)."""
    title_match = _PAGE_TITLE.search(html)
    extra_match = _PAGE_EXTRA.search(html)
    extra = _clean(extra_match.group(1)) if extra_match else ""
    # «members» бывает у групп и чатов: это не канал, в каталог не берём
    count = re.match(r"([\d\s.,KkMm]+)\s+subscribers", extra)
    if not count:
        return ChannelInfo(kind=PageKind.NOT_FOUND)
    return ChannelInfo(
        kind=PageKind.CLOSED,
        title=_clean(title_match.group(1)) if title_match else None,
        subscribers=parse_count(count.group(1)),
    )
