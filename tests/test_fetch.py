from datetime import date
from pathlib import Path

import httpx

from ru_ai_channels.catalog import Stat
from ru_ai_channels.fetch import FetchResult, fetch_all, fetch_channel, merge_stat
from ru_ai_channels.parser import ChannelInfo, PageKind

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 12)


def client_with(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=transport, follow_redirects=True)


def test_fetch_channel_parses_a_successful_response() -> None:
    html = (FIXTURES / "feed_open.html").read_text(encoding="utf-8")
    client = client_with(httpx.MockTransport(lambda _: httpx.Response(200, text=html)))

    result = fetch_channel(client, "test_channel")

    assert result.error is None
    assert result.info is not None
    assert result.info.subscribers == 96_400


def test_fetch_channel_does_not_retry_on_404() -> None:
    calls: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    result = fetch_channel(client_with(httpx.MockTransport(handler)), "x_channel")

    assert result.info is None
    assert result.error == "HTTP 404"
    assert len(calls) == 1


def test_fetch_channel_reports_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("нет соединения", request=request)

    result = fetch_channel(client_with(httpx.MockTransport(handler)), "x_channel", retries=0)

    assert result.info is None
    assert result.error is not None
    assert "ConnectError" in result.error


def test_fetch_all_pauses_between_requests_but_not_before_the_first() -> None:
    client = client_with(httpx.MockTransport(lambda _: httpx.Response(200, text="<html/>")))
    pauses: list[float] = []

    fetch_all(client, ["aaaaa", "bbbbb", "ccccc"], delay=1.5, sleep=pauses.append)

    assert pauses == [1.5, 1.5]


def test_merge_keeps_previous_stat_on_error() -> None:
    previous = Stat(subscribers=100, last_post="2026-11-01T10:00:00+00:00", checked="2026-11-11")

    merged = merge_stat(previous, FetchResult("a", None, "HTTP 500"), TODAY)

    assert merged == previous


def test_merge_returns_none_when_channel_disappeared() -> None:
    result = FetchResult("a", ChannelInfo(kind=PageKind.NOT_FOUND))

    assert merge_stat(Stat(subscribers=5), result, TODAY) is None


def test_merge_records_closed_feed() -> None:
    result = FetchResult("a", ChannelInfo(kind=PageKind.CLOSED, subscribers=4))

    merged = merge_stat(None, result, TODAY)

    assert merged == Stat(subscribers=4, last_post=None, checked="2026-11-12", feed_open=False)
