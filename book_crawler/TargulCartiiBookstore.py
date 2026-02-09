import asyncio
from time import sleep

from bs4 import BeautifulSoup
import os
import time
from book_crawler.BaseBookstore import BaseBookstore
from book_framework.core.Book import Book, Offer,BookCategory
from book_framework.utils import log

TARGUL_CARTII_BASE_URL = "https://www.targulcartii.ro/"
TARGUL_CARTII_NAME = "Targul Cartii"
TARGUL_CARTII_PAGE_QUERY = "?limit=40&page=%s"

CONCURRENT_TAB = 1
LOAD_WAIT = 2

class TargulCartii(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(add_book_callback)
        self._scanned_pages = 0
        self.cats = {
            BookCategory.LITERATURE: ["https://www.targulcartii.ro/literatura", "https://www.targulcartii.ro/carti-in-limba-straina"],
            BookCategory.KIDS_YA: ["https://www.targulcartii.ro/carti-pentru-copii"],
            BookCategory.ARTS: ["https://www.targulcartii.ro/arta-si-arhitectura"],
            BookCategory.SCIENCE: ["https://www.targulcartii.ro/dictionare-cultura-educatie", "https://www.targulcartii.ro/stiinta-si-tehnica"],
            BookCategory.HISTORY: ["https://www.targulcartii.ro/istorie-si-etnografie"],
            BookCategory.SPIRITUALITY : ["https://www.targulcartii.ro/spiritualitate"],
            BookCategory.HOBBIES: ["https://www.targulcartii.ro/hobby-si-ghiduri"]
        }

    async def my_data_handler(self, url, html):
        self._scanned_pages += 1
        if "Pagina cautata nu exista pe acest site!" in html:
            return
        soup = BeautifulSoup(html, 'html.parser')
        book_rows = soup.find(class_="product-grid").find_all(class_="product-list-row")
        for book_row in book_rows:
            try:
                title_tag = book_row.find(class_="name").find("a")
                book_url = book_row.find(class_="name").find("a").get('href')
                author_tag = book_row.find(class_="name").find(class_="author_name")
                isbn_tag = None
                price_tag = book_row.find(class_="price_value")
                if not title_tag or not price_tag:
                    continue # need at least title and price

                title = title_tag.get("title")
                author = author_tag.get_text() if author_tag else None
                isbn = isbn_tag.get_text() if isbn_tag else None
                price = float(price_tag.get_text().replace("LEI",'').strip())

                book = Book(
                    title=title,
                    author=author,
                    isbn=isbn,
                    category = next((cat for cat, urls in self.cats.items() if any(u in url for u in urls)), BookCategory.NONE),
                    offers=[Offer(TARGUL_CARTII_NAME, book_url, price)]
                )
                self.add_book(book)
            except Exception as e:
                log(f"Caught {e}")

    def get_all_urls(self):
        self.get_web_scraper(profile='fast')
        urls = []
        for url in [url for urls in self.cats.values() for url in urls]:
            request_result = self.web_scraper.load_page(url + TARGUL_CARTII_PAGE_QUERY % 1)
            soup = BeautifulSoup(request_result, 'html.parser')
            max_pages = int(soup.find("span", class_="pagination_total_pages").get_text())
            for i in range(max_pages):
                urls.append(url + TARGUL_CARTII_PAGE_QUERY % (i+1))
        self.destroy_scraper_thread()

        return urls

    def get_books(self, urls):
        self.get_web_scraper(profile='slow')
        # Get all URLs
        asyncio.run(self.web_scraper.async_scrape(
            urls=urls if urls is not None else self.get_all_urls(),
            load_callback=self.my_data_handler,
            max_concurrent=CONCURRENT_TAB,
            additional_wait=LOAD_WAIT,
            wait_for_selector=".content-loaded"
        ))

        print(f"Finished scanning {self._scanned_pages} pages")

    def _log_progress(self, urls):
        """Log scraping progress."""
        total = len(urls)
        while not self._stop_logging:
            progress = (self._scanned_pages / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_pages}/{total} ({progress:.1f}%)")
            time.sleep(2)
