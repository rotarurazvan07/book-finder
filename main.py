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
  python -m main --mode prepare-scrape
  python -m main --mode scrape --books_db_path chunk-1.db --urls "url1,url2,..."
  python -m main --mode prepare-rate --books_db_path books.db --chunks_dir ./chunks
  python -m main --mode rate --books_db_path rate_chunk-1.db --urls ./chunks/task-1.json
  python -m main --mode merge --books_db_path books.db --chunks_dir ./chunks
  python -m main --mode apply-rates --books_db_path books.db --chunks_dir ./chunks
"""

import argparse
import json
import math
import os
import random
import sys
import sqlite3
import threading
from collections import defaultdict
from contextlib import redirect_stdout
from types import SimpleNamespace
from urllib.parse import urlparse

from book_framework.BooksManager import BooksManager
from book_framework.SettingsManager import SettingsManager
from book_framework.core.Goodreads import rateBooks

# ─────────────────────────────────────────────────────────────────────────────
# Bookstore Registry
# ─────────────────────────────────────────────────────────────────────────────

_STORE_KEYS = {
    "targulcartii":   lambda: _import("book_crawler.TargulCartiiBookstore",   "TargulCartii"),
    "anticariat-unu": lambda: _import("book_crawler.AnticariatUnuBookstore", "AnticariatUnu"),
    # "printrecarti":   lambda: _import("book_crawler.PrintreCartiBookstore",  "PrintreCarti"),
}

_RUNNER_SETS = {
    "actions": ["targulcartii", "anticariat-unu"], # Grouping them like in bet-assistant
    "all":     list(_STORE_KEYS.keys()),
    "test":    ["targulcartii"],
}

MAX_RUNNERS = {"actions": 100, "all": 100, "test": 1}


def _import(module: str, cls: str):
    import importlib
    return getattr(importlib.import_module(module), cls)


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

def mode_prepare_scrape(runner: str):
    store_classes = get_runner_classes(runner)
    if not store_classes:
        print("❌ No stores found for runner type.", file=sys.stderr)
        sys.exit(1)

    urls = []
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        for cls in store_classes:
            instance = cls(None)
            try:
                new_urls = instance.get_urls()
                if not new_urls:
                    print(f"⚠️  No URLs found for {cls.__name__}", file=sys.stderr)
                urls.extend(new_urls)
            except Exception as e:
                print(f"❌ Error in {cls.__name__}.get_urls(): {e}", file=sys.stderr)
            finally:
                del instance

    random.shuffle(urls)
    max_runners = MAX_RUNNERS.get(runner, 100)
    chunk_size  = max(20, math.ceil(len(urls) / max_runners))

    tasks = [
        {
            "books_db_path": f"chunk-{i // chunk_size + 1}.db",
            "urls":    ",".join(urls[i : i + chunk_size]),
        }
        for i in range(0, len(urls), chunk_size)
    ]

    print(json.dumps(tasks))


# ─────────────────────────────────────────────────────────────────────────────
# Mode: scrape
# ─────────────────────────────────────────────────────────────────────────────

def mode_scrape(books_db_path: str, urls_str: str):
    if os.path.isfile(urls_str):
        with open(urls_str, "r") as f:
            urls = [u.strip() for u in f.read().split(",") if u.strip()]
    else:
        urls = [u.strip() for u in urls_str.split(",") if u.strip()]

    groups: dict = defaultdict(list)
    for url in urls:
        domain    = urlparse(url).netloc
        core_name = domain.split(".")[-2] if "." in domain else domain
        groups[core_name].append(url)

    db_manager = BooksManager(books_db_path)
    db_manager.reset_db()

    def _on_book(book):
        db_manager.add_book(book)

    for i, (domain_key, group_urls) in enumerate(groups.items()):
        print(f"  [{i+1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)...")
        try:
            store = get_store_class(group_urls[0])(_on_book)
            store.get_books(group_urls)
        except Exception as e:
            print(f"    ⚠️ Error scraping {domain_key}: {e}", file=sys.stderr)
        finally:
            del store

    db_manager.close()
    print(f"✅ Scrape complete. Database saved to: {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: prepare-rate
# ─────────────────────────────────────────────────────────────────────────────

def mode_prepare_rate(books_db_path: str, chunks_dir: str):
    if not os.path.exists(books_db_path):
        print(f"❌ Database not found: {books_db_path}", file=sys.stderr)
        sys.exit(1)

    db_manager = BooksManager(books_db_path)
    books_df = db_manager.fetch_all_as_dataframe()
    db_manager.close()

    # Identify books to rate
    to_rate_df = books_df[books_df['rating'].isna() | (books_df['rating'] == 0)].copy()
    columns_to_keep = ['rowid', 'title', 'author', 'isbn']
    existing_cols = [c for c in columns_to_keep if c in to_rate_df.columns]
    to_rate_df = to_rate_df[existing_cols]
    to_rate_df = to_rate_df.where(to_rate_df.notnull(), None)
    records = to_rate_df.to_dict('records')

    if not records:
        print(json.dumps([]))
        return

    chunk_size = max(20, math.ceil(len(records) / 100))
    tasks = []

    base_name = os.path.splitext(os.path.basename(books_db_path))[0]
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        chunk_id = i // chunk_size + 1

        json_file_path = os.path.join(chunks_dir, f"{base_name}_rate_{chunk_id}.json")
        output_books_db_path = f"{base_name}_rate_{chunk_id}.db"

        # Preserve the JSON creation requested by user
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)

        tasks.append({
            "books_db_path":    output_books_db_path,
            "urls":          json_file_path
        })

    print(json.dumps(tasks))


# ─────────────────────────────────────────────────────────────────────────────
# Mode: rate
# ─────────────────────────────────────────────────────────────────────────────

def mode_rate(books_db_path: str, urls_str: str):
    conn = sqlite3.connect(books_db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_results (
            rid INTEGER PRIMARY KEY,
            rating REAL,
            goodreads_url TEXT
        )
    """)
    conn.commit()
    db_lock = threading.Lock()

    try:
        with open(urls_str, 'r', encoding='utf-8') as f:
            books_to_rate = json.load(f)
        books = [SimpleNamespace(**b) for b in books_to_rate]
    except Exception as e:
        print(f"❌ Failed to read or parse {urls_str}: {e}", file=sys.stderr)
        sys.exit(1)

    def _save_rating_to_chunk(rowid, rating, goodreads_url):
        if rating is None or goodreads_url is None:
            return
        with db_lock:
            cursor.execute(
                "INSERT OR REPLACE INTO rate_results (rid, rating, goodreads_url) VALUES (?, ?, ?)",
                (rowid, rating, goodreads_url)
            )
            conn.commit()
        print(f"  ✔️ Saved: Row {rowid} -> {rating} stars")

    print(f"🚀 Starting rating for {len(books)} books from {urls_str}")
    rateBooks(books, _save_rating_to_chunk)

    conn.close()
    print(f"🏁 Finished. Results saved in {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: merge
# ─────────────────────────────────────────────────────────────────────────────

def mode_merge(books_db_path: str, chunks_dir: str):
    if not os.path.isdir(chunks_dir):
        print(f"❌ Not a valid directory: {chunks_dir}", file=sys.stderr)
        sys.exit(1)

    BooksManager.merge_databases(chunks_dir, books_db_path)
    print(f"✅ Merged into {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: apply-rates
# ─────────────────────────────────────────────────────────────────────────────

def mode_apply_rates(books_db_path: str, chunks_dir: str):
    main_db_abs = os.path.abspath(books_db_path)
    main_db_filename = os.path.basename(main_db_abs)

    chunk_files = [
        f for f in os.listdir(chunks_dir)
        if f.endswith(".db") and f != main_db_filename and "_rate_" in f
    ]

    print(f"📂 Found {len(chunk_files)} rating chunks in {chunks_dir}")

    main_conn = sqlite3.connect(main_db_abs)
    cursor = main_conn.cursor()

    for cf in chunk_files:
        chunk_path = os.path.join(chunks_dir, cf)
        print(f"  💉 Processing {cf}...")
        try:
            cursor.execute(f"ATTACH DATABASE ? AS chunk_db", (chunk_path,))
            cursor.execute("""
                UPDATE books
                SET
                    rating = (SELECT rating FROM chunk_db.rate_results WHERE chunk_db.rate_results.rid = books.rowid),
                    goodreads_url = (SELECT goodreads_url FROM chunk_db.rate_results WHERE chunk_db.rate_results.rid = books.rowid)
                WHERE EXISTS (
                    SELECT 1 FROM chunk_db.rate_results WHERE chunk_db.rate_results.rid = books.rowid
                )
            """)
            main_conn.commit()
            cursor.execute("DETACH DATABASE chunk_db")
            print(f"  ✅ Successfully merged {cf}")
        except Exception as e:
            print(f"  ⚠️ Error merging {cf}: {e}", file=sys.stderr)
            try: cursor.execute("DETACH DATABASE chunk_db")
            except: pass

    main_conn.close()
    print(f"🏁 Final Rated Database saved at: {books_db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Book Finder CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--mode", required=True,
                   choices=["prepare-scrape", "scrape", "prepare-rate", "rate", "merge", "apply-rates"])
    p.add_argument("--books_db_path",      help="Path to the main SQLite DB",     default="books.db")
    p.add_argument("--urls",         help="Comma-separated URLs to scrape or path to JSON task file", default="")
    p.add_argument("--chunks_dir",   help="Directory for chunk storage",    default=".")
    p.add_argument("--config_path",  help="Directory for config files",     default="config")
    p.add_argument("--runners",      help="Runner set to use", choices=list(_RUNNER_SETS.keys()), default="all")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    settings_manager = SettingsManager(args.config_path)
    from book_framework.SimilarityEngine import SimilarityEngine
    SimilarityEngine(settings_manager.get('similarity_config') or {})

    if args.mode == "prepare-scrape":
        mode_prepare_scrape(args.runners)

    elif args.mode == "scrape":
        if not args.urls:
            build_parser().error("--urls and --books_db_path are required for scrape")
        mode_scrape(args.books_db_path, args.urls)

    elif args.mode == "prepare-rate":
        mode_prepare_rate(args.books_db_path, args.chunks_dir)

    elif args.mode == "rate":
        if not args.urls:
            build_parser().error("--urls and --books_db_path are required for rate")
        mode_rate(args.books_db_path, args.urls)

    elif args.mode == "merge":
        mode_merge(args.books_db_path, args.chunks_dir)

    elif args.mode == "apply-rates":
        mode_apply_rates(args.books_db_path, args.chunks_dir)