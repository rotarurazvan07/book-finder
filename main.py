import argparse
from contextlib import redirect_stdout
import json
import math
import base64
import os
import sqlite3
import sys
import threading
import time
from types import SimpleNamespace
from book_framework.DatabaseManager import DatabaseManager, merge_databases
from book_framework.SettingsManager import settings_manager
from book_crawler.TargulCartiiBookstore import TargulCartii
from book_crawler.AnticariatUnuBookstore import AnticariatUnu
# from book_crawler.PrintreCartiBookstore import PrintreCarti

from book_framework.core.Book import Book, BookCategory
from book_framework.core.Goodreads import rateBooks
from book_framework.utils import log

MAX_GITHUB_RUNNERS = 200

def addRating(rowid, rating, goodreads_url):
    if rating is not None and goodreads_url is not None:
        db_manager.update_rating_callback(rowid, rating, goodreads_url)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Book Finder Scraper")

    parser.add_argument(
            "--mode",
            choices=["prepare-scrape", "scrape", "prepare-rate", "rate", "apply-rates", "merge"],
            required=True,
            help="The phase of the workflow to execute"
        )

    parser.add_argument("--store", help="Store Name", default="TargulCartii", choices=["TargulCartii", "AnticariatUnu", "PrintreCarti"])
    parser.add_argument("--db_path", help="Path to the SQLite database file (e.g., books.db)", default="books.db")
    parser.add_argument("--urls", help="Urls to scrape", default="")
    parser.add_argument("--books_data", help="Book objects to rate", default="")
    parser.add_argument("--chunks_dir", help="Where are the chunk stored", default=".")

    args = parser.parse_args()

    settings_manager.load_settings("config")

    if args.mode == "prepare-scrape":
        if not args.store:
            parser.error("requires --store")
            sys.exit(1)

        store = getattr(sys.modules[__name__], args.store)(None)

        with open(os.devnull, 'w') as f:
            with redirect_stdout(f):
                urls = store.get_all_urls()

        CHUNK_SIZE = max(20, math.ceil(len(urls) / MAX_GITHUB_RUNNERS))

        all_tasks = []

        for i in range(0, len(urls), CHUNK_SIZE):
            chunk = urls[i : i + CHUNK_SIZE]
            all_tasks.append({
                "db_path": f"{args.store}{i // CHUNK_SIZE + 1}.db",
                "store": args.store,
                "urls": ",".join(chunk)
            })

        print(json.dumps(all_tasks))
    elif args.mode == "scrape":
        if not args.urls or not args.db_path or not args.store:
            parser.error("requires --urls and --db_path and --store")
            sys.exit(1)

        db_manager = DatabaseManager(args.db_path)
        db_manager.reset_db()
        def _add_book_callback(book):
            db_manager.add_book(book)

        store = getattr(sys.modules[__name__], args.store)(_add_book_callback)

        print(f"🚀 Scraping into {args.db_path} for {args.store}...")

        url_list = [u.strip() for u in args.urls.split(",") if u.strip()]
        start = time.perf_counter()
        store.get_books(urls=url_list)

        db_manager.close()

        print(f"✅ Scrape complete. Database saved to: {args.db_path}")
    elif args.mode == "prepare-rate":
        if not args.db_path or not args.chunks_dir:
            parser.error("requires --db_path --chunks_dir")
            sys.exit(1)

        with open(os.devnull, 'w') as f:
            with redirect_stdout(f):
                db_manager = DatabaseManager(args.db_path)
                books_df = db_manager.fetch_all_as_dataframe()

        to_rate_df = books_df[books_df['rating'].isna() | (books_df['rating'] == 0)].copy()
        columns_to_keep = ['rowid', 'title', 'author', 'isbn']
        existing_cols = [c for c in columns_to_keep if c in to_rate_df.columns]
        to_rate_df = to_rate_df[existing_cols]

        to_rate_df = to_rate_df.where(to_rate_df.notnull(), None)
        records = to_rate_df.to_dict('records')

        if not records:
            print(json.dumps([]))
            sys.exit(0)

        CHUNK_SIZE = max(20, math.ceil(len(records) / MAX_GITHUB_RUNNERS))
        all_tasks = []

        for i in range(0, len(records), CHUNK_SIZE):
            chunk = records[i : i + CHUNK_SIZE]
            chunk_id = i // CHUNK_SIZE + 1

            json_file_path = os.path.join(args.chunks_dir, f"{args.db_path.replace('.db','')}_rate_{chunk_id}.json")
            output_db_path = f"{args.db_path.replace('.db','')}_rate_{chunk_id}.db"

            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2)

            all_tasks.append({
                "db_path": output_db_path,
                "books_data": json_file_path
            })
        print(json.dumps(all_tasks))
    elif args.mode == "rate":
        if not args.books_data or not args.db_path:
            parser.error("Rate mode requires --books_data and --db_path")
            sys.exit(1)
        conn = sqlite3.connect(args.db_path, check_same_thread=False)
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
            with open(args.books_data, 'r', encoding='utf-8') as f:
                books_to_rate = json.load(f)
            books = [SimpleNamespace(**b) for b in books_to_rate]
        except Exception as e:
            print(f"❌ Failed to read or parse {args.books_data}: {e}")
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
            print(f"✔️ Saved: Row {rowid} -> {rating} stars")

        print(f"🚀 Starting rating for {len(books)} books from {args.books_data}")
        rateBooks(books, _save_rating_to_chunk)

        conn.close()
        print(f"🏁 Finished. Results saved in {args.db_path}")
    elif args.mode == "merge":
        if not args.chunks_dir or not args.db_path or not os.path.isdir(args.chunks_dir):
            print(f"❌ Error: {args.chunks_dir} is not a valid directory.")
            sys.exit(1)
        merge_databases(args.chunks_dir, args.db_path)
    elif args.mode == "apply-rates":
        if not args.db_path or not args.chunks_dir:
            parser.error("Apply-rates requires --db_path and --chunks_dir")
            sys.exit(1)

        main_db_abs = os.path.abspath(args.db_path)
        main_db_filename = os.path.basename(main_db_abs)

        chunk_files = [
            f for f in os.listdir(args.chunks_dir)
            if f.endswith(".db")
            and f != main_db_filename
        ]

        print(f"📂 Found {len(chunk_files)} rating chunks in {args.chunks_dir}")

        main_conn = sqlite3.connect(main_db_filename)
        cursor = main_conn.cursor()

        for cf in chunk_files:
            chunk_path = os.path.join(args.chunks_dir, cf)
            print(f"💉 Processing {cf}...")

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
                print(f"✅ Successfully merged {cf}")

            except Exception as e:
                print(f"⚠️ Error merging {cf}: {e}")
                # Try to detach if it failed mid-process
                try:
                    cursor.execute("DETACH DATABASE chunk_db")
                except:
                    pass

        main_conn.close()
        print(f"🏁 Final Rated Database saved at: {args.db_path}")