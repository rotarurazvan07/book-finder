from __future__ import annotations

import os
from collections import OrderedDict

import pandas as pd
from scrape_kit import BufferedStorageManager, get_logger
from scrape_kit.errors import StorageError

from .core.Book import Book

logger = get_logger(__name__)


class BooksManager(BufferedStorageManager):
    """Buffered SQLite manager for books."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path, "books")

    # ── Schema ──────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        with self.db_lock:
            self.conn.execute("""
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
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_title ON books(title)")
            self.conn.commit()

    # ── Flush: preserve schema/indexes ───────────────────────────────────────

    def flush(self) -> None:
        if not self._dirty:
            return
        df = self.ensure_buffer()
        with self.db_lock:
            try:
                self.conn.execute("DELETE FROM books")
                if not df.empty:
                    df.to_sql("books", self.conn, if_exists="append", index=False)
                self.conn.commit()
                self._dirty = False
            except Exception as exc:
                raise StorageError(f"BooksManager flush failed: {exc}") from exc

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_book(self, book: Book) -> None:
        """Saves every offer in the Book object as a row in the buffer."""
        title = getattr(book, "title", None)
        if not isinstance(title, str) or not title.strip():
            logger.warning("Skipping book with invalid title: %s", title)
            return

        self.ensure_buffer()
        category = getattr(book.category, "value", None)

        for offer in book.offers:
            self.insert(
                {
                    "isbn": book.isbn,
                    "title": title.strip(),
                    "author": book.author,
                    "category": category,
                    "rating": book.rating,
                    "goodreads_url": book.goodreads_url,
                    "store": offer.store,
                    "url": offer.url,
                    "price": offer.price,
                }
            )

        logger.debug("Saved %s + %s", book.title, book.author)

    def fetch_all_as_dataframe(self) -> pd.DataFrame:
        """Retrieves books as a pandas DataFrame with synthetic rowid."""
        self.reopen_if_changed()
        df = self.ensure_buffer().copy()

        if df.empty:
            # Keep expected shape for downstream callers.
            df.insert(0, "rowid", pd.Series(dtype="int64"))
            df["category"] = pd.Series(dtype="object")
            return df

        # Existing flows expect rowid; when using buffered storage, index maps 1:1
        # with persisted order after reset/scrape cycles.
        df.insert(0, "rowid", df.index + 1)
        df["category"] = df["category"].fillna("").str.split(r"\s*,\s*")
        df["category"] = df["category"].apply(lambda x: [i for i in x if i])
        return df

    def update_rating_callback(
        self, rowid: int, rating: float, goodreads_url: str
    ) -> None:
        """Updates rating fields in buffer by rowid-like index."""
        if rating is None or goodreads_url is None:
            return

        self.ensure_buffer()
        idx = int(rowid) - 1
        if idx < 0 or idx >= len(self._buffer):
            return

        self._buffer.at[idx, "rating"] = rating
        self._buffer.at[idx, "goodreads_url"] = goodreads_url
        self._dirty = True

    def reset_db(self) -> None:
        self.clear_database("books")
        logger.info("Database cleared.")

    @classmethod
    def merge_databases(cls, input_dir: str, output_file: str) -> None:
        """Merge chunk DBs using bulk staging + SQL deduplication + category cleanup."""
        if os.path.exists(output_file):
            os.remove(output_file)

        manager = cls(output_file)
        manager.reset_db()
        
        # Step 1: Bulk merge all chunks into staging table (fast)
        report = super(BooksManager, manager).merge_databases(input_dir, "books")
        
        # Step 2: Deduplicate from staging into books using SQL aggregation
        with manager.db_lock:
            manager.conn.execute("""
                INSERT INTO books (isbn, title, author, category, rating, goodreads_url, store, url, price)
                SELECT 
                    MAX(isbn),
                    MAX(title),
                    MAX(author),
                    GROUP_CONCAT(category, '|'),  -- Use pipe delimiter temporarily
                    MAX(rating),
                    MAX(goodreads_url),
                    MAX(store),
                    url,
                    MIN(price)
                FROM staging_books
                WHERE url IS NOT NULL 
                  AND title IS NOT NULL 
                  AND TRIM(title) != ''
                GROUP BY url
            """)
            manager.conn.commit()
            
            # Step 3: Fix categories in-place (single pass over final deduplicated data)
            rows = manager.conn.execute("SELECT rowid, category FROM books WHERE category IS NOT NULL").fetchall()
            for row_id, cat_str in rows:
                if not cat_str:
                    continue
                # Split by both | (from GROUP_CONCAT) and , (within each field)
                tokens = set()
                for segment in cat_str.split('|'):
                    for token in segment.split(','):
                        clean = token.strip()
                        if clean:
                            tokens.add(clean)
                
                clean_category = ", ".join(sorted(tokens)) if tokens else None
                manager.conn.execute(
                    "UPDATE books SET category = ? WHERE rowid = ?",
                    (clean_category, row_id)
                )
            
            manager.conn.commit()
            
            # Cleanup staging table
            manager.conn.execute("DROP TABLE IF EXISTS staging_books")
            manager.conn.commit()
        
        manager.close()
        
        if report.errors:
            for err in report.errors:
                logger.warning("Merge chunk warning: %s", err)
        
        logger.info(
            "FINISHED merge: chunks=%d, skipped=%d",
            report.processed_chunks,
            report.skipped_chunks,
        )