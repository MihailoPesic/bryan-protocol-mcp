"""CLI entrypoint for bryan-protocol-mcp (MCP server, ingestion pipeline, and local queries)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bryan_protocol_mcp.db import DEFAULT_DATA_DIR, DEFAULT_DB_PATH, ProtocolDatabase
from bryan_protocol_mcp.scraper import (
    scrape_all_youtube,
    scrape_blueprint_articles,
    scrape_blueprint_extra,
    scrape_bryanjohnson_essays,
    scrape_protocol_museum,
    scrape_protocol_pages,
)
from bryan_protocol_mcp.server import run_http_server, run_stdio_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bryan-protocol-mcp",
        description="Ground-truth knowledge base and MCP server for Bryan Johnson's Blueprint Protocol.",
    )
    sub = parser.add_subparsers(dest="command")

    # serve
    p_serve = sub.add_parser("serve", help="Run the MCP server (default: stdio).")
    p_serve.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Scrape official protocol, museum, essays, products, Kate Tolo, and YouTube.")
    p_ingest.add_argument("--protocol", action="store_true", help="Scrape protocol.bryanjohnson.com")
    p_ingest.add_argument("--museum", action="store_true", help="Scrape protocol-museum.bryanjohnson.com")
    p_ingest.add_argument("--articles", action="store_true", help="Scrape blueprint.bryanjohnson.com blog articles")
    p_ingest.add_argument("--extra", action="store_true", help="Scrape Blueprint/Immortals products, pages, and katetolo.com")
    p_ingest.add_argument("--essays", action="store_true", help="Scrape bryanjohnson.com articles/essays")
    p_ingest.add_argument("--youtube", action="store_true", help="Scrape @BryanJohnson, @katetolo, and external podcasts")
    p_ingest.add_argument("--all", action="store_true", help="Run all scrapers and rebuild the database")
    p_ingest.add_argument("--refresh", action="store_true", help="Re-scrape cached YouTube transcripts")
    p_ingest.add_argument("--workers", type=int, default=6)
    p_ingest.add_argument("--max-videos", type=int, default=None)
    p_ingest.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p_ingest.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    # build-db
    p_build = sub.add_parser("build-db", help="Rebuild SQLite + FTS5 database from JSON files in data/.")
    p_build.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p_build.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    # query
    p_query = sub.add_parser("query", help="Query the local database from the terminal.")
    p_query.add_argument("text", help="Question or search phrase")
    p_query.add_argument("--mode", choices=["wwbd", "protocol", "stance", "search"], default="wwbd")
    p_query.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    # stats
    p_stats = sub.add_parser("stats", help="Print database counts and Tier 1 official pages.")
    p_stats.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    args = parser.parse_args(argv)
    cmd = args.command or "serve"

    if cmd == "serve":
        transport = getattr(args, "transport", "stdio")
        db_path = getattr(args, "db", DEFAULT_DB_PATH)
        if transport == "http":
            run_http_server(host=args.host, port=args.port, db_path=str(db_path))
        else:
            run_stdio_server(db_path=str(db_path))
        return 0

    if cmd == "ingest":
        run_all = args.all or not (
            args.protocol or args.museum or args.articles or args.extra or args.essays or args.youtube
        )
        report: dict[str, object] = {}
        if run_all or args.protocol:
            pages = scrape_protocol_pages(args.data_dir)
            report["protocol_pages"] = len(pages)
            print(f"[ingest] protocol.bryanjohnson.com: {len(pages)} pages", file=sys.stderr)
        if run_all or args.museum:
            museum = scrape_protocol_museum(args.data_dir)
            report["museum_docs"] = len(museum)
            print(f"[ingest] protocol-museum.bryanjohnson.com: {len(museum)} docs", file=sys.stderr)
        if run_all or args.articles:
            arts = scrape_blueprint_articles(args.data_dir)
            report["blueprint_articles"] = len(arts)
            print(f"[ingest] blueprint.bryanjohnson.com articles: {len(arts)} articles", file=sys.stderr)
        if run_all or args.extra:
            extra = scrape_blueprint_extra(args.data_dir)
            report["extra_docs"] = len(extra)
            print(f"[ingest] blueprint/immortals/katetolo extra: {len(extra)} docs", file=sys.stderr)
        if run_all or args.essays:
            essays = scrape_bryanjohnson_essays(args.data_dir)
            report["essays"] = len(essays)
            print(f"[ingest] bryanjohnson.com essays: {len(essays)} essays", file=sys.stderr)
        if run_all or args.youtube:
            yt_summary = scrape_all_youtube(
                args.data_dir,
                workers=args.workers,
                refresh=args.refresh,
                max_videos=args.max_videos,
            )
            report["youtube"] = yt_summary
            print(f"[ingest] youtube: {yt_summary}", file=sys.stderr)

        db = ProtocolDatabase(args.db)
        counts = db.rebuild_from_data_dir(args.data_dir)
        report["db_counts"] = counts
        print(json.dumps(report, indent=2))
        return 0

    if cmd == "build-db":
        counts = ProtocolDatabase(args.db).rebuild_from_data_dir(args.data_dir)
        print(json.dumps(counts, indent=2))
        return 0

    if cmd == "query":
        db = ProtocolDatabase(args.db)
        if args.mode == "wwbd":
            out = db.what_would_bryan_do(args.text)
        elif args.mode == "protocol":
            out = db.get_official_protocol(args.text)
        elif args.mode == "stance":
            out = db.check_stance_and_changes(args.text)
        else:
            out = db.search_archive(args.text)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if cmd == "stats":
        print(json.dumps(ProtocolDatabase(args.db).get_protocol_overview(), indent=2, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
