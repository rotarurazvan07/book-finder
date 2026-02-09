import glob
import os
import sqlite3
import threading
import pandas as pd
from .core.Book import Book
from .utils import log

import sqlite3
import os
import glob

def merge_databases(input_dir, output_file):
    search_path = os.path.join(input_dir, "*.db")
    db_files = [os.path.abspath(f) for f in glob.glob(search_path)]
    output_abs_path = os.path.abspath(output_file)
    db_files = [f for f in db_files if f != output_abs_path]

    if not db_files:
        print(f"❌ No .db files found in {input_dir}")
        return

    # Delete existing output file to start fresh and avoid index conflicts
    if os.path.exists(output_file):
        os.remove(output_file)

    main_conn = sqlite3.connect(output_file)
    cursor = main_conn.cursor()

    # 🚀 Optimization: Use memory for temp storage and skip disk safety checks
    cursor.execute("PRAGMA synchronous = OFF")
    cursor.execute("PRAGMA journal_mode = MEMORY")
    cursor.execute("PRAGMA temp_store = MEMORY")

    # 1. Create a staging table (This one ALLOWS duplicates)
    cursor.execute("""
        CREATE TABLE staging_books (
            isbn TEXT, title TEXT, author TEXT, category TEXT,
            rating REAL, goodreads_url TEXT, store TEXT, url TEXT, price REAL
        )
    """)

    # 2. Fast Dump: Just copy everything from every chunk
    for db_file in db_files:
        try:
            if os.path.getsize(db_file) < 100: continue

            cursor.execute(f"ATTACH DATABASE ? AS chunk", (db_file,))
            cursor.execute("INSERT INTO staging_books SELECT * FROM chunk.books")
            main_conn.commit()
            cursor.execute("DETACH DATABASE chunk")
            print(f"📥 Dumped {os.path.basename(db_file)}")
        except Exception as e:
            print(f"❌ Failed {os.path.basename(db_file)}: {e}")
            try: cursor.execute("DETACH DATABASE chunk")
            except: pass

    print("⚡ Staging complete. Processing duplicates and categories...")

    # 3. Create the final table with the unique index
    cursor.execute("""
        CREATE TABLE books (
            isbn TEXT, title TEXT NOT NULL, author TEXT, category TEXT,
            rating REAL, goodreads_url TEXT, store TEXT, url TEXT, price REAL
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX idx_url_unique ON books(url)")

    # 4. THE MAGIC QUERY: Group by URL and concatenate categories
    # This replaces the slow Step B with one single pass
    cursor.execute("""
        INSERT INTO books (isbn, title, author, category, rating, goodreads_url, store, url, price)
        SELECT
            MAX(isbn), title, author,
            GROUP_CONCAT(DISTINCT category),
            MAX(rating), MAX(goodreads_url), store, url, MIN(price)
        FROM staging_books
        GROUP BY url
    """)

    # 5. Cleanup
    cursor.execute("DROP TABLE staging_books")
    main_conn.commit()

    cursor.execute("SELECT COUNT(*) FROM books")
    print(f"🏁 FINISHED! Total unique books: {cursor.fetchone()[0]}")
    main_conn.close()

class DatabaseManager:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.row_factory = sqlite3.Row
        self.db_lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        # Every row is a distinct offer.
        # Title/Author/ISBN are repeated for each store.
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS books (
                isbn TEXT,
                title TEXT NOT NULL,
                author TEXT,
                category TEXT,
                rating REAL,
                goodreads_url TEXT,
                store TEXT,
                url TEXT,
                price REAL
            )
        ''')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_title ON books(title)')
        self.conn.commit()

    def add_book(self, book: Book):
        """Saves every offer as a new row. No merging, no collisions."""
        try:
            for offer in book.offers:
                with self.db_lock:
                    self.conn.execute('''
                        INSERT INTO books (
                            isbn, title, author, category, rating,
                            goodreads_url, store, url, price
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        book.isbn,
                        book.title,
                        book.author,
                        book.category.value,
                        book.rating,
                        book.goodreads_url,
                        offer.store,
                        offer.url,
                        offer.price
                    ))
                    self.conn.commit()
            log(f"Saved {book.title} + {book.author} + {book.category}")
        except Exception as e:
            log(f"Database Error: {e}")

    def fetch_all_as_dataframe(self) -> pd.DataFrame:
        """Standard fetch. Data is already flat, so no processing needed."""
        return pd.read_sql_query("SELECT rowid, * FROM books", self.conn)

    def update_rating_callback(self, rowid, rating, goodreads_url):
        if rating is not None and goodreads_url is not None:
            with self.db_lock:
                self.conn.execute(
                    "UPDATE books SET rating = ?, goodreads_url = ? WHERE rowid = ?",
                    (rating, goodreads_url, rowid)
                )
                self.conn.commit()

    def reset_db(self):
        self.conn.execute('DELETE FROM books')
        self.conn.commit()
        log("Database cleared for new daily scrape.")

    def close(self):
        self.conn.commit()
        # 1. Flush the logs into the main file
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        # 2. Transition back to a single-file mode (deletes the -wal file)
        self.conn.execute("PRAGMA journal_mode=DELETE;")
        # 3. Clean up the connection
        self.conn.close()