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

    # ── Schema ────────────────────────────────────────────────────────────────

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
                    df.to_sql(
                        "books", self.conn, if_exists="append", index=False
                    )
                self.conn.commit()
                self._dirty = False
            except Exception as exc:
                raise StorageError(f"BooksManager flush failed: {exc}") from exc

    # ── Public API ────────────────────────────────────────────────────────────

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
        """Merge chunk DBs into a fresh output DB, deduplicated by URL."""
        if os.path.exists(output_file):
            os.remove(output_file)

        manager = cls(output_file)
        manager.reset_db()
        buf0 = manager.ensure_buffer()
        url_to_idx: dict[str, int] = (
            {str(u): int(i) for i, u in buf0["url"].items() if pd.notna(u)} if not buf0.empty else {}
        )

        processed = 0
        deduped = 0

        def _merge_categories(existing: str | None, incoming: str | None) -> str | None:
            ordered = OrderedDict()
            for raw in (existing, incoming):
                if not raw:
                    continue
                for token in str(raw).split(","):
                    item = token.strip()
                    if item:
                        ordered[item] = True
            if not ordered:
                return None
            return ", ".join(ordered.keys())

        def _max_text(a: str | None, b: str | None) -> str | None:
            values = [v for v in (a, b) if v not in (None, "")]
            if not values:
                return None
            return max(values)

        def _max_num(a, b):
            vals = [v for v in (a, b) if v is not None]
            if not vals:
                return None
            return max(vals)

        def _min_num(a, b):
            vals = [v for v in (a, b) if v is not None]
            if not vals:
                return None
            return min(vals)

        def _row(row) -> None:
            nonlocal processed, deduped
            processed += 1
            payload = dict(row)
            url = payload.get("url")
            if not url:
                return
            title = payload.get("title")
            if not isinstance(title, str) or not title.strip():
                return

            buf = manager.ensure_buffer()
            idx = url_to_idx.get(url)
            if idx is None:
                buf.loc[len(buf)] = payload
                manager._dirty = True
                idx = len(buf) - 1
                url_to_idx[url] = idx
                return

            deduped += 1
            buf.at[idx, "isbn"] = _max_text(buf.at[idx, "isbn"], payload.get("isbn"))
            buf.at[idx, "category"] = _merge_categories(
                buf.at[idx, "category"], payload.get("category")
            )
            buf.at[idx, "rating"] = _max_num(
                buf.at[idx, "rating"], payload.get("rating")
            )
            buf.at[idx, "goodreads_url"] = _max_text(
                buf.at[idx, "goodreads_url"], payload.get("goodreads_url")
            )
            buf.at[idx, "price"] = _min_num(buf.at[idx, "price"], payload.get("price"))
            manager._dirty = True

        report = manager.merge_row_by_row(
            input_dir,
            "books",
            row_callback=_row,
            flush_callback=manager.flush,
            read_batch_size=2000,
            flush_every_rows=10000,
        )
        manager.flush()
        manager.close()

        if report.errors:
            for err in report.errors:
                logger.warning("Merge chunk warning: %s", err)
        logger.info(
            "FINISHED merge: processed=%d, chunks=%d, deduped=%d, skipped=%d",
            processed,
            report.processed_chunks,
            deduped,
            report.skipped_chunks,
        )
