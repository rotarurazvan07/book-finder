from abc import abstractmethod, ABC
from typing import Callable

from book_framework.WebScraper import WebScraper, ScrapeMode

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
        WebScraper.scrape(urls, callback, mode=mode, max_concurrency=max_concurrency)

    def add_book(self, book) -> bool:
        """Add a book via callback."""
        try:
            self.add_book_callback(book)
            return True
        except Exception as e:
            print(f"Error while adding book: {e}")
            return False