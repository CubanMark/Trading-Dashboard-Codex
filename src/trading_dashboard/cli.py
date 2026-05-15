from __future__ import annotations

import argparse

from .compute.metrics import compute_all_metrics
from .config import Settings
from .data.fetch import fetch_prices
from .data.storage import init_db, log_run
from .render.html import render_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trading-dashboard")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("--pages", default=None, help="Output directory for rendered HTML pages")
    parser.add_argument("--universe", default=None, help="Universe CSV path")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["init-db", "fetch", "compute", "render", "update"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--mock", action="store_true", help="Use deterministic offline mock data")
        cmd.add_argument("--years", type=int, default=5)

    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    settings = Settings(years=args.years)
    if args.db or args.pages or args.universe:
        from pathlib import Path

        settings = Settings(
            db_path=Path(args.db) if args.db else settings.db_path,
            pages_dir=Path(args.pages) if args.pages else settings.pages_dir,
            universe_csv_path=Path(args.universe) if args.universe else settings.universe_csv_path,
            years=args.years,
        )
    return settings


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = settings_from_args(args)

    if args.command == "init-db":
        init_db(settings.db_path)
        log_run(settings.db_path, "init-db", "ok", "Database initialized")
        return 0
    if args.command == "fetch":
        init_db(settings.db_path)
        fetch_prices(settings, use_mock=args.mock)
        log_run(settings.db_path, "fetch", "ok", "Prices fetched")
        return 0
    if args.command == "compute":
        init_db(settings.db_path)
        compute_all_metrics(settings)
        log_run(settings.db_path, "compute", "ok", "Metrics computed")
        return 0
    if args.command == "render":
        init_db(settings.db_path)
        render_site(settings)
        log_run(settings.db_path, "render", "ok", "Site rendered")
        return 0
    if args.command == "update":
        init_db(settings.db_path)
        fetch_prices(settings, use_mock=args.mock)
        compute_all_metrics(settings)
        render_site(settings)
        log_run(settings.db_path, "update", "ok", "Full update complete")
        return 0

    parser.error("Unknown command")
    return 2
