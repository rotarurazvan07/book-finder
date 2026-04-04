from __future__ import annotations


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

    def merge_databases(self, input_dir: str) -> None:
        """Merge chunk DBs using bulk staging + SQL deduplication + category cleanup."""
        # Bulk merge + Single SQL step for deduplication and category merging
        dedup_query = """
            INSERT INTO books (isbn, title, author, category, rating, goodreads_url, store, url, price)
            WITH RECURSIVE
              -- Part 1: Split categories from staging_books by comma
              split(url, part, rest) AS (
                SELECT url, '', category || ',' FROM staging_books WHERE category IS NOT NULL
                UNION ALL
                SELECT url,
                       TRIM(substr(rest, 0, instr(rest, ','))),
                       substr(rest, instr(rest, ',') + 1)
                FROM split WHERE rest <> ''
              ),
              -- Part 2: Extract unique parts per URL
              unique_cats AS (
                SELECT url, part FROM split WHERE part <> '' GROUP BY url, part
              ),
              -- Part 3: Re-join into a single sorted string
              merged_cats AS (
                SELECT url, GROUP_CONCAT(part, ',') as cleaned_category
                FROM (SELECT url, part FROM unique_cats ORDER BY url, part)
                GROUP BY url
              )
            SELECT
                MAX(s.isbn),
                MAX(s.title),
                MAX(s.author),
                m.cleaned_category,
                MAX(s.rating),
                MAX(s.goodreads_url),
                MAX(s.store),
                s.url,
                MIN(s.price)
            FROM staging_books s
            LEFT JOIN merged_cats m ON s.url = m.url
            WHERE s.url IS NOT NULL
              AND s.title IS NOT NULL
              AND TRIM(s.title) != ''
            GROUP BY s.url
        """
        report = super().merge_databases(
            input_dir, "books", end_process_query=dedup_query
        )

        if report.errors:
            for err in report.errors:
                logger.warning("Merge chunk warning: %s", err)

        logger.info(
            "FINISHED merge: chunks=%d, skipped=%d",
            report.processed_chunks,
            report.skipped_chunks,
        )
