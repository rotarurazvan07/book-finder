import sqlite3
import pandas as pd
from .core.Book import Book
from .utils import log
from .SettingsManager import settings_manager

class DatabaseManager:
    def __init__(self, db_path: str = None):
        settings_manager.load_settings("config")
        cfg = settings_manager.get_config('database_config')

        if db_path is None:
            db_path = cfg.get('db_path', 'data/books.db')

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.row_factory = sqlite3.Row
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
            log(f"Saved {len(book.offers)} entries for: {book.title}")
        except Exception as e:
            log(f"Database Error: {e}")

    def fetch_all_as_dataframe(self) -> pd.DataFrame:
        """Standard fetch. Data is already flat, so no processing needed."""
        return pd.read_sql_query("SELECT rowid, * FROM books", self.conn)

    def update_rating_callback(self, rowid, rating, goodreads_url):
        if rating is not None and goodreads_url is not None:
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
        self.conn.close()