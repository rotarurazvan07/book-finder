"""
main.py — Book Finder CLI
──────────────────────────
Modes:
  prepare-scrape   Collect bookstore URLs and split them into chunks for parallel scraping.
  scrape           Scrape a chunk of URLs into a local SQLite DB.
  prepare-rate     Identify books without ratings and prepare JSON tasks for rating.
  rate             Scrape Goodreads/Google ratings for a batch of books.
  merge            Merge all chunk DBs into a single final DB.
  apply-rates      Inject rating results from chunks back into the main DB.

Usage examples:
  python -m main --mode prepare-scrape --runners actions --config_dir ./config
  python -m main --mode scrape --books_db_path scrape_actions_1.db --urls "url1,url2,..." --config_dir ./config
  python -m main --mode prepare-rate --books_db_path books.db --chunks_dir ./chunks
  python -m main --mode rate --books_db_path rate_books_1.db --urls ./chunks/task-1.json --config_dir ./config
  python -m main --mode merge --books_db_path books.db --chunks_dir ./chunks --config_dir ./config
  python -m main --mode apply-rates --books_db_path books.db --chunks_dir ./chunks
"""

import argparse
import json
import math
import os
import random
import sqlite3
import sys
import threading
from collections import defaultdict
from contextlib import redirect_stdout
from types import SimpleNamespace
from urllib.parse import urlparse

from scrape_kit import SettingsManager, configure, get_logger

logger = get_logger(__name__)

from book_framework.BooksManager import BooksManager
from book_framework.core.Goodreads import rateBooks

# ─────────────────────────────────────────────────────────────────────────────
# Bookstore registry
# ─────────────────────────────────────────────────────────────────────────────

_STORE_KEYS = {
    "targulcartii": lambda: _import("TargulCartii"),
    "anticariat-unu": lambda: _import("AnticariatUnu"),
    # "printrecarti": lambda: _import("PrintreCarti"),
}

_RUNNER_SETS = {
    "actions": ["targulcartii", "anticariat-unu"],
    "all": list(_STORE_KEYS.keys()),
    "test": ["targulcartii"],
}

MAX_CHUNK_SIZE = {"actions": 100, "all": 100, "test": 1}


def _import(cls: str):
    from book_crawler import bookstores

    return getattr(bookstores, cls)


def get_store_class(url: str):
    lower = url.lower()
    for key, loader in _STORE_KEYS.items():
        if key in lower:
            return loader()
    raise ValueError(f"No store registered for URL: {url}")


def get_runner_classes(runner: str) -> list:
    keys = _RUNNER_SETS.get(runner, [])
    return [_STORE_KEYS[k]() for k in keys]


# ─────────────────────────────────────────────────────────────────────────────
# Mode: prepare-scrape
# ─────────────────────────────────────────────────────────────────────────────


def mode_prepare_scrape(runner: str, config_dir: str) -> None:
    configure(config_dir)

    store_classes = get_runner_classes(runner)
    if not store_classes:
        logger.error("❌ No stores found for runner type.")
        sys.exit(1)

    urls = []
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        for cls in store_classes:
            instance = cls(None)
            for attempt in range(3):
                try:
                    new_urls = instance.get_urls()
                    if new_urls:
                        urls.extend(new_urls)
                        break
                    logger.warning(
                        f"⚠️  No URLs found for {cls.__name__} (attempt {attempt + 1}/3)"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Error in {cls.__name__}.get_urls() (attempt {attempt + 1}/3): {e}"
                    )

                if attempt < 2:
                    import time

                    time.sleep(2)
            del instance

    random.shuffle(urls)

    unique_domains = sorted(list({urlparse(u).netloc for u in urls if u}))
    logger.info(
        f"Collected {len(urls)} URLs across {len(unique_domains)} domains: {', '.join(unique_domains)}"
    )

    max_runners = MAX_CHUNK_SIZE[runner]
    chunk_size = max(20, math.ceil(len(urls) / max_runners))

    tasks = [
        {
            "books_db_path": f"scrape_{runner}_{i // chunk_size + 1}.db",
            "urls": ",".join(urls[i : i + chunk_size]),
        }
        for i in range(0, len(urls), chunk_size)
    ]

    sys.stdout.write(json.dumps(tasks) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: scrape
# ─────────────────────────────────────────────────────────────────────────────


def mode_scrape(books_db_path: str, urls_str: str, config_dir: str) -> None:
    configure(config_dir)

    if os.path.isfile(urls_str):
        with open(urls_str, encoding="utf-8") as f:
            urls = [u.strip() for u in f.read().split(",") if u.strip()]
    else:
        urls = [u.strip() for u in urls_str.split(",") if u.strip()]

    groups: dict = defaultdict(list)
    for url in urls:
        domain = urlparse(url).netloc
        core_name = domain.split(".")[-2] if "." in domain else domain
        groups[core_name].append(url)

    # Initialize SettingsManager locally to match bet-assistant flow.
    SettingsManager(config_dir)

    books_manager = BooksManager(books_db_path)
    books_manager.reset_db()

    def _on_book(book) -> None:
        books_manager.add_book(book)

    for i, (domain_key, group_urls) in enumerate(groups.items()):
        logger.info(
            f"  [{i + 1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)..."
        )
        try:
            store = get_store_class(group_urls[0])(_on_book)
            store.get_books(group_urls)
        except Exception as e:
            logger.error(f"    ⚠️ Error scraping {domain_key}: {e}")

    books_manager.close()
    logger.info(f"✅ Scrape complete. Database saved to: {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: prepare-rate
# ─────────────────────────────────────────────────────────────────────────────


def mode_prepare_rate(books_db_path: str, chunks_dir: str) -> None:
    if not os.path.exists(books_db_path):
        logger.error(f"❌ Database not found: {books_db_path}")
        sys.exit(1)

    books_manager = BooksManager(books_db_path)
    books_df = books_manager.fetch_all_as_dataframe()
    books_manager.close()

    to_rate_df = books_df[books_df["rating"].isna() | (books_df["rating"] == 0)].copy()
    columns_to_keep = ["rowid", "title", "author", "isbn"]
    existing_cols = [c for c in columns_to_keep if c in to_rate_df.columns]
    to_rate_df = to_rate_df[existing_cols]
    to_rate_df = to_rate_df.where(to_rate_df.notnull(), None)
    records = to_rate_df.to_dict("records")

    if not records:
        sys.stdout.write("[]\n")
        return

    chunk_size = max(20, math.ceil(len(records) / 100))
    tasks = []

    base_name = os.path.splitext(os.path.basename(books_db_path))[0]
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        chunk_id = i // chunk_size + 1

        json_file_path = os.path.join(chunks_dir, f"rate_{base_name}_{chunk_id}.json")
        output_books_db_path = f"rate_{base_name}_{chunk_id}.db"

        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)

        tasks.append({"books_db_path": output_books_db_path, "urls": json_file_path})

    sys.stdout.write(json.dumps(tasks) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: rate
# ─────────────────────────────────────────────────────────────────────────────


def mode_rate(books_db_path: str, urls_str: str, config_dir: str) -> None:
    configure(config_dir)

    conn = sqlite3.connect(books_db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_results (
            rid INTEGER PRIMARY KEY,
            rating REAL,
            goodreads_url TEXT
        )
        """
    )
    conn.commit()
    db_lock = threading.Lock()

    try:
        with open(urls_str, encoding="utf-8") as f:
            books_to_rate = json.load(f)
        books = [SimpleNamespace(**b) for b in books_to_rate]
    except Exception as e:
        logger.error(f"❌ Failed to read or parse {urls_str}: {e}")
        sys.exit(1)

    def _save_rating_to_chunk(rowid, rating, goodreads_url) -> None:
        if rating is None or goodreads_url is None:
            return
        with db_lock:
            cursor.execute(
                "INSERT OR REPLACE INTO rate_results (rid, rating, goodreads_url) VALUES (?, ?, ?)",
                (rowid, rating, goodreads_url),
            )
            conn.commit()
        logger.info(f"  ✔️ Saved: Row {rowid} -> {rating} stars")

    similarity_config = (
        SettingsManager(config_dir).get("similarity_config") if config_dir else None
    )
    if not similarity_config:
        build_parser().error(
            "--config_dir with similarity_config.yaml is required for rate"
        )

    logger.info(f"🚀 Starting rating for {len(books)} books from {urls_str}")
    rateBooks(books, _save_rating_to_chunk, similarity_config=similarity_config)

    conn.close()
    logger.info(f"🏁 Finished. Results saved in {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: merge
# ─────────────────────────────────────────────────────────────────────────────


def mode_merge(books_db_path: str, chunks_dir: str, config_dir: str) -> None:
    if not os.path.isdir(chunks_dir):
        logger.error(f"❌ Not a valid directory: {chunks_dir}")
        sys.exit(1)

    # Initialize SettingsManager locally to match bet-assistant flow.
    SettingsManager(config_dir)

    BooksManager.merge_databases(chunks_dir, books_db_path)
    logger.info(f"✅ Merged into {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: apply-rates
# ─────────────────────────────────────────────────────────────────────────────


def mode_apply_rates(books_db_path: str, chunks_dir: str) -> None:
    main_db_abs = os.path.abspath(books_db_path)
    main_db_filename = os.path.basename(main_db_abs)

    all_candidate_dbs = [
        f for f in os.listdir(chunks_dir) if f.endswith(".db") and f != main_db_filename
    ]
    chunk_files: list[str] = []

    for cf in all_candidate_dbs:
        chunk_path = os.path.join(chunks_dir, cf)
        conn = None
        try:
            conn = sqlite3.connect(chunk_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rate_results' LIMIT 1"
            )
            if cur.fetchone():
                chunk_files.append(cf)
        except Exception as e:
            logger.warning("Skipping %s during rate_results scan: %s", cf, e)
        finally:
            if conn:
                conn.close()

    logger.info(
        "📂 Found %d rating chunks (by rate_results table) in %s",
        len(chunk_files),
        chunks_dir,
    )

    main_conn = sqlite3.connect(main_db_abs)
    cursor = main_conn.cursor()

    for cf in chunk_files:
        chunk_path = os.path.join(chunks_dir, cf)
        logger.info(f"  💉 Processing {cf}...")
        try:
            cursor.execute("ATTACH DATABASE ? AS chunk_db", (chunk_path,))
            cursor.execute(
                """
                UPDATE books
                SET
                    rating = (SELECT rating FROM chunk_db.rate_results WHERE chunk_db.rate_results.rid = books.rowid),
                    goodreads_url = (SELECT goodreads_url FROM chunk_db.rate_results WHERE chunk_db.rate_results.rid = books.rowid)
                WHERE EXISTS (
                    SELECT 1 FROM chunk_db.rate_results WHERE chunk_db.rate_results.rid = books.rowid
                )
                """
            )
            main_conn.commit()
            cursor.execute("DETACH DATABASE chunk_db")
            logger.info(f"  ✅ Successfully merged {cf}")
        except Exception as e:
            logger.error(f"  ⚠️ Error merging {cf}: {e}")
            try:
                cursor.execute("DETACH DATABASE chunk_db")
            except Exception:
                pass

    main_conn.close()
    logger.info(f"🏁 Final Rated Database saved at: {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Book Finder CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mode",
        required=True,
        choices=[
            "prepare-scrape",
            "scrape",
            "prepare-rate",
            "rate",
            "merge",
            "apply-rates",
        ],
    )
    p.add_argument("--books_db_path", help="Path to the main SQLite DB")
    p.add_argument(
        "--urls",
        help="Comma-separated URLs to scrape or path to JSON task file",
    )
    p.add_argument("--chunks_dir", help="Directory for chunk storage")
    p.add_argument("--config_dir", help="Directory containing config files")
    # Backward-compatible alias.
    p.add_argument("--config_path", dest="config_dir", help=argparse.SUPPRESS)
    p.add_argument("--runners", choices=list(_RUNNER_SETS.keys()))
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.mode == "prepare-scrape":
        if not args.runners or not args.config_dir:
            build_parser().error(
                "--runners and --config_dir are required for prepare-scrape"
            )
        mode_prepare_scrape(args.runners, args.config_dir)

    elif args.mode == "scrape":
        if not args.urls or not args.books_db_path or not args.config_dir:
            build_parser().error(
                "--urls, --books_db_path, and --config_dir are required for scrape"
            )
        mode_scrape(args.books_db_path, args.urls, args.config_dir)

    elif args.mode == "prepare-rate":
        if not args.books_db_path or not args.chunks_dir:
            build_parser().error(
                "--books_db_path and --chunks_dir are required for prepare-rate"
            )
        mode_prepare_rate(args.books_db_path, args.chunks_dir)

    elif args.mode == "rate":
        if not args.urls or not args.books_db_path or not args.config_dir:
            build_parser().error(
                "--urls, --books_db_path, and --config_dir are required for rate"
            )
        mode_rate(args.books_db_path, args.urls, args.config_dir)

    elif args.mode == "merge":
        if not args.books_db_path or not args.chunks_dir or not args.config_dir:
            build_parser().error(
                "--books_db_path, --chunks_dir, and --config_dir are required for merge"
            )
        mode_merge(args.books_db_path, args.chunks_dir, args.config_dir)

    elif args.mode == "apply-rates":
        if not args.books_db_path or not args.chunks_dir:
            build_parser().error(
                "--books_db_path and --chunks_dir are required for apply-rates"
            )
        mode_apply_rates(args.books_db_path, args.chunks_dir)
