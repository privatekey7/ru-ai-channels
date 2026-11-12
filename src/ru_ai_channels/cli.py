"""Командная строка: update (обновить данные и README), render (только README), probe."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from .catalog import load_catalog, load_stats, load_updated, save_stats
from .fetch import fetch_all, make_client, merge_stat
from .parser import PageKind
from .render import render_readme

ROOT = Path(__file__).resolve().parents[2]
CHANNELS = ROOT / "data" / "channels.toml"
STATS = ROOT / "data" / "stats.json"
TEMPLATE = ROOT / "templates" / "README.md.tmpl"
README = ROOT / "README.md"


def build_readme() -> str:
    catalog = load_catalog(CHANNELS)
    stats = load_stats(STATS)
    updated = load_updated(STATS)
    # «Молчащие» считаются на дату обновления данных: README воспроизводим без сети и часов.
    today = date.fromisoformat(updated) if updated else datetime.now(UTC).date()
    template = TEMPLATE.read_text(encoding="utf-8")
    return render_readme(template, catalog, stats, today, updated)


def cmd_update(delay: float) -> int:
    catalog = load_catalog(CHANNELS)
    stats = load_stats(STATS)
    today = datetime.now(UTC).date()
    handles = [c.handle for c in catalog.channels]
    with make_client() as client:
        results = fetch_all(client, handles, delay=delay)
    failed = [r for r in results if r.error]
    for r in results:
        key = r.handle.lower()
        new = merge_stat(stats.get(key), r, today)
        if new is None:
            print(f"ВНИМАНИЕ: {r.handle} не найден на t.me, проверьте вручную", file=sys.stderr)
            stats.pop(key, None)
        else:
            stats[key] = new
    for r in failed:
        print(f"ошибка {r.handle}: {r.error} (оставлены прежние данные)", file=sys.stderr)
    if len(failed) == len(results):
        print("Ни один канал не загрузился: данные не тронуты.", file=sys.stderr)
        return 1
    save_stats(STATS, stats, today.isoformat())
    README.write_text(build_readme(), encoding="utf-8", newline="\n")
    print(f"Обновлено: {len(results) - len(failed)}/{len(results)} каналов")
    return 0


def cmd_render() -> int:
    README.write_text(build_readme(), encoding="utf-8", newline="\n")
    return 0


def cmd_check() -> int:
    """Код 1, если README не соответствует данным (для CI)."""
    current = README.read_text(encoding="utf-8") if README.exists() else ""
    if current != build_readme():
        print("README.md устарел: запустите `uv run ru-ai-channels render`", file=sys.stderr)
        return 1
    return 0


def cmd_probe(handles: list[str], delay: float) -> int:
    with make_client() as client:
        for r in fetch_all(client, handles, delay=delay):
            if r.info is None:
                print(f"{r.handle}\tERROR\t{r.error}")
            elif r.info.kind is PageKind.NOT_FOUND:
                print(f"{r.handle}\tNOT_FOUND")
            else:
                last = r.info.last_post.date().isoformat() if r.info.last_post else "-"
                print(
                    f"{r.handle}\t{r.info.kind.value}\t{r.info.subscribers}\t{last}\t{r.info.title}"
                )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ru-ai-channels", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("update", "probe"):
        p = sub.add_parser(name)
        p.add_argument("--delay", type=float, default=2.0, help="пауза между запросами, с")
        if name == "probe":
            p.add_argument("handles", nargs="+")
    sub.add_parser("render", help="пересобрать README без сети")
    sub.add_parser("check", help="проверить, что README соответствует данным")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command == "update":
        return cmd_update(args.delay)
    if args.command == "probe":
        return cmd_probe(args.handles, args.delay)
    if args.command == "render":
        return cmd_render()
    return cmd_check()


if __name__ == "__main__":
    raise SystemExit(main())
