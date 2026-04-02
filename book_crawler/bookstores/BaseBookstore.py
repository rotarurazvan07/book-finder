from abc import abstractmethod, ABC
from typing import Callable

from scrape_kit import ScrapeMode, get_logger, scrape

logger = get_logger(__name__)

class BaseBookstore(ABC):
    def __init__(self, add_book_callback: Callable):
        super().__init__()
        self.add_book_callback = add_book_callback

    @abstractmethod
    def get_urls(self):
        """Return list of URLs to scrape."""
        raise NotImplementedError()

    @abstractmethod
    def get_books(self, urls):
        raise NotImplementedError()

    @abstractmethod
    def _parse_page(self, url, html):
        """Parse a single scraped page. Used as callback for scrape_urls()."""
        raise NotImplementedError()

    def scrape_urls(self, urls, callback, mode=ScrapeMode.FAST, max_concurrency=1):
        """Scrape URLs with concurrency, calling callback(url, html) for each page."""
        logger.info(
            "Starting scrape for %d URLs (mode=%s, concurrency=%d)",
            len(urls),
            mode,
            max_concurrency,
        )
        scrape(urls, callback, mode=mode, max_concurrency=max_concurrency)
        logger.info("Finished scrape batch")

    def add_book(self, book) -> bool:
        """Add a book via callback."""
        try:
            title = getattr(book, "title", None)
            if not isinstance(title, str) or not title.strip():
                logger.warning(
                    "Skipping invalid book with missing title (author=%s, offers=%s)",
                    getattr(book, "author", None),
                    len(getattr(book, "offers", []) or []),
                )
                return False

            offers = getattr(book, "offers", None) or []
            if not offers:
                logger.warning("Skipping book without offers: %s", title.strip())
                return False

            self.add_book_callback(book)
            logger.info("Book added: %s by %s", book.title, book.author)
            return True
        except Exception as e:
            logger.error("Error while adding book: %s", e)
            return False
