import glob
import os
import sqlite3
import threading
import pandas as pd
from typing import List, Optional, Set
from .core.Book import Book
from .utils import log
from .exceptions import DatabaseError

class BooksManager:
    """Manages the SQLite database for book storage and rating updates."""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.row_factory = sqlite3.Row
        self.db_lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        """Initializes the database schema."""
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

    @classmethod
    def merge_databases(cls, input_dir: str, output_file: str):
        """Class method to merge multiple chunk databases into a single master database."""
        db_files = cls._get_db_files(input_dir, output_file)
        if not db_files:
            return

        # Start fresh
        if os.path.exists(output_file):
            os.remove(output_file)

        main_conn = sqlite3.connect(output_file)
        try:
            cls._perform_merge(main_conn, db_files)
            print(f"🏁 FINISHED! Master database created at {output_file}")
        finally:
            main_conn.close()

    @staticmethod
    def _get_db_files(input_dir: str, skip_file: str) -> List[str]:
        search_path = os.path.join(input_dir, "*.db")
        candidates = [os.path.abspath(f) for f in glob.glob(search_path)]
        skip_abs = os.path.abspath(skip_file)
        return [f for f in candidates if f != skip_abs]

    @classmethod
    def _perform_merge(cls, main_conn, db_files: List[str]):
        cursor = main_conn.cursor()
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")

        # 1. Staging
        cursor.execute("""
            CREATE TABLE staging_books (
                isbn TEXT, title TEXT, author TEXT, category TEXT,
                rating REAL, goodreads_url TEXT, store TEXT, url TEXT, price REAL
            )
        """)

        for db_file in db_files:
            try:
                if os.path.getsize(db_file) < 100: continue
                cursor.execute("ATTACH DATABASE ? AS chunk", (db_file,))
                cursor.execute("INSERT INTO staging_books SELECT * FROM chunk.books")
                main_conn.commit()
                cursor.execute("DETACH DATABASE chunk")
                print(f"📥 Dumped {os.path.basename(db_file)}")
            except sqlite3.Error as e:
                print(f"❌ Failed to merge {os.path.basename(db_file)}: {e}")

        # 2. Final Deduplication
        cursor.execute("""
            CREATE TABLE books (
                isbn TEXT, title TEXT NOT NULL, author TEXT, category TEXT,
                rating REAL, goodreads_url TEXT, store TEXT, url TEXT, price REAL
            )
        """)
        cursor.execute("CREATE UNIQUE INDEX idx_url_unique ON books(url)")
        cursor.execute("""
            INSERT INTO books (isbn, title, author, category, rating, goodreads_url, store, url, price)
            SELECT MAX(isbn), title, author, GROUP_CONCAT(DISTINCT category), MAX(rating), MAX(goodreads_url), store, url, MIN(price)
            FROM staging_books GROUP BY url
        """)
        cursor.execute("DROP TABLE staging_books")
        main_conn.commit()

    def add_book(self, book: Book):
        """Saves every offer in the Book object as a new row."""
        try:
            with self.db_lock:
                for offer in book.offers:
                    self.conn.execute('''
                        INSERT INTO books (isbn, title, author, category, rating, goodreads_url, store, url, price)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (book.isbn, book.title, book.author, book.category.value, book.rating, book.goodreads_url, offer.store, offer.url, offer.price))
                self.conn.commit()
            log(f"Saved {book.title} + {book.author}")
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to add book {book.title}: {e}")

    def fetch_all_as_dataframe(self) -> pd.DataFrame:
        """Retrieves books as a pandas DataFrame."""
        df = pd.read_sql_query("SELECT rowid, * FROM books", self.conn)
        df['category'] = df['category'].fillna("").str.split(r'\s*,\s*')
        df['category'] = df['category'].apply(lambda x: [i for i in x if i])
        return df

    def update_rating_callback(self, rowid: int, rating: float, goodreads_url: str):
        """Callback to update a book's rating and Goodreads URL."""
        if rating is not None and goodreads_url is not None:
            with self.db_lock:
                self.conn.execute("UPDATE books SET rating = ?, goodreads_url = ? WHERE rowid = ?", (rating, goodreads_url, rowid))
                self.conn.commit()

    def reset_db(self):
        """Clears all records from the books table."""
        with self.db_lock:
            self.conn.execute('DELETE FROM books')
            self.conn.commit()
        log("Database cleared.")

    def close(self):
        """Safely closes the database connection."""
        try:
            self.conn.commit()
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            self.conn.execute("PRAGMA journal_mode=DELETE;")
            self.conn.close()
        except sqlite3.Error:
            pass # Connection already closed or fatal error