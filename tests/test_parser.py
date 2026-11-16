from datetime import UTC, datetime
from pathlib import Path

import pytest

from ru_ai_channels.parser import PageKind, parse_channel_page, parse_count

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("920", 920),
        ("96.4K", 96_400),
        ("141K", 141_000),
        ("1.2M", 1_200_000),
        ("1 020", 1_020),
        ("2\xa0651", 2_651),
        ("abc", None),
        ("", None),
    ],
)
def test_parse_count_understands_telegram_formats(raw: str, expected: int | None) -> None:
    assert parse_count(raw) == expected


def test_open_feed_gives_subscribers_and_decoded_title() -> None:
    info = parse_channel_page(load("feed_open.html"))

    assert info.kind is PageKind.FEED
    assert info.subscribers == 96_400
    assert info.title == "Тестовый & канал"


def test_open_feed_last_post_is_the_latest_date_regardless_of_order() -> None:
    info = parse_channel_page(load("feed_open.html"))

    assert info.last_post == datetime(2026, 11, 12, 12, 43, 31, tzinfo=UTC)


def test_feed_without_posts_keeps_subscribers_and_has_no_last_post() -> None:
    info = parse_channel_page(load("feed_no_posts.html"))

    assert info.kind is PageKind.FEED
    assert info.subscribers == 1_020
    assert info.last_post is None


def test_closed_feed_card_gives_subscribers_only() -> None:
    info = parse_channel_page(load("card_closed.html"))

    assert info.kind is PageKind.CLOSED
    assert info.subscribers == 4
    assert info.title == "Закрытая лента"
    assert info.last_post is None


def test_group_card_gives_members() -> None:
    info = parse_channel_page(load("card_group.html"))

    assert info.kind is PageKind.GROUP
    assert info.subscribers == 2_651
    assert info.last_post is None


def test_user_card_is_not_a_channel() -> None:
    assert parse_channel_page(load("card_user.html")).kind is PageKind.NOT_FOUND


def test_garbage_html_is_not_found() -> None:
    assert parse_channel_page("<html>captcha</html>").kind is PageKind.NOT_FOUND
