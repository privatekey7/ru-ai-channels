"""Загрузка страниц t.me/s с вежливыми паузами и понятной обработкой ошибок."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import httpx

from .catalog import Stat
from .parser import ChannelInfo, PageKind, parse_channel_page

log = logging.getLogger(__name__)

PROXY_ENV = "RU_AI_CHANNELS_PROXY"  # например socks5h://127.0.0.1:10808
USER_AGENT = "ru-ai-channels/0.1 (catalog updater; once a day)"


@dataclass(frozen=True)
class FetchResult:
    handle: str
    info: ChannelInfo | None
    error: str | None = None


def make_client(timeout: float = 20.0) -> httpx.Client:
    """Клиент; прокси берётся из переменной окружения, по умолчанию его нет."""
    proxy = os.environ.get(PROXY_ENV) or None
    return httpx.Client(
        proxy=proxy,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
    )


def fetch_channel(client: httpx.Client, handle: str, retries: int = 2) -> FetchResult:
    url = f"https://t.me/s/{handle}"
    last_error = "неизвестная ошибка"
    for attempt in range(retries + 1):
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code == 200:
                return FetchResult(handle, parse_channel_page(response.text))
            last_error = f"HTTP {response.status_code}"
            if response.status_code not in (429, 500, 502, 503, 504):
                break
        if attempt < retries:
            time.sleep(2.0 * (attempt + 1))
    return FetchResult(handle, None, last_error)


def fetch_all(
    client: httpx.Client,
    handles: list[str],
    delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[FetchResult]:
    results: list[FetchResult] = []
    for i, handle in enumerate(handles):
        if i:
            sleep(delay)
        result = fetch_channel(client, handle)
        log.info("%s: %s", handle, result.error or result.info)
        results.append(result)
    return results


def merge_stat(previous: Stat | None, result: FetchResult, today: date) -> Stat | None:
    """Новая статистика канала. Ошибка сети оставляет прежнее значение.

    None означает, что канал пропал (нет такого канала) и его надо проверить вручную.
    """
    if result.info is None:
        return previous
    info = result.info
    if info.kind is PageKind.NOT_FOUND:
        return None
    return Stat(
        subscribers=info.subscribers,
        last_post=info.last_post.isoformat() if info.last_post else None,
        checked=today.isoformat(),
        feed_open=info.kind is PageKind.FEED,
    )
