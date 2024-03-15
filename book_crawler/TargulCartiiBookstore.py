from time import sleep

from bs4 import BeautifulSoup
import os
import time
from book_crawler.BaseBookstore import BaseBookstore
from book_framework.core.Book import Book, Offer,BookCategory
from book_framework.utils import log

TARGUL_CARTII_BASE_URL = "https://www.targulcartii.ro/"
TARGUL_CARTII_NAME = "Targul Cartii"
TARGUL_CARTII_PAGE_QUERY = "noutati?limit=40&page=%s"

NUM_THREADS = os.cpu_count()

class TargulCartii(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(add_book_callback)
        self._scanned_pages = 0

    @property
    def category_map(self) -> dict:
        return {
            "Literatura": BookCategory.LITERATURE,
            "Bibliofilie": BookCategory.LITERATURE,      # Rare/Collectable books are still Literature
            "Carti pentru copii": BookCategory.KIDS_YA,
            "Arta si Arhitectura": BookCategory.ARTS,
            "Dictionare, Cultura, Educatie": BookCategory.SCIENCE, # Reference & Education fits Science/Academic
            "Istorie si etnografie": BookCategory.HISTORY,
            "Stiinta si tehnica": BookCategory.SCIENCE,
            "Spiritualitate": BookCategory.SPIRITUALITY,
            "Hobby si ghiduri": BookCategory.HOBBIES,
            "Carti in limba straina": BookCategory.LITERATURE # Usually fiction, otherwise maps to LITERATURE as a catch-all
        }

    def get_books(self):
        # Build urls to scrape
        self.get_web_scraper(profile='slow')
        max_pages = 1
        request_result = self.web_scraper.fast_http_request(TARGUL_CARTII_BASE_URL + TARGUL_CARTII_PAGE_QUERY % "0")
        if request_result is not None:
            soup = BeautifulSoup(request_result, 'html.parser')
            max_pages = int(soup.find("span", class_="pagination_total_pages").get_text())
        self.destroy_scraper_thread()

        # Get all URLs
        urls = []
        for current_page in range(1, max_pages):
            urls.append(TARGUL_CARTII_BASE_URL + TARGUL_CARTII_PAGE_QUERY % current_page)

        # Create a shared scraper
        self.get_web_scraper(profile='fast')
        self.run_workers(urls, self._find_books_job, num_threads=NUM_THREADS)
        self.destroy_scraper_thread()

        print(f"Finished scanning {self._scanned_pages} pages")

    def _log_progress(self, urls):
        """Log scraping progress."""
        total = len(urls)
        while not self._stop_logging:
            progress = (self._scanned_pages / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_pages}/{total} ({progress:.1f}%)")
            time.sleep(2)

    def _find_books_job(self, urls, thread_id):
        try:
            for url in urls:
                self._scanned_pages += 1

                request_result = self.web_scraper.load_page(url)
                try:
                    html = BeautifulSoup(request_result, 'html.parser')
                    book_urls = set([a.get('href') for div in html.find_all('div', class_="product-list-preview-btn") for a in div.find_all('a')])
                    for book_url in book_urls:
                        request_result = self.web_scraper.load_page(book_url)
                        try:
                            if "STOC EPUIZAT!" in request_result:
                                continue

                            soup = BeautifulSoup(request_result, 'html.parser')

                            # TODO better anchors
                            title_tag = soup.find(class_="titlu_carte")
                            author_tag = soup.find("span", itemprop="author")
                            isbn_tag = (tag := soup.find(string=lambda x: "ISBN" in x if x else False)) and (p := tag.find_parent('div')) and p.find_next_sibling('div')
                            price_tag = soup.find("span", class_="price-new")
                            category_tag = soup.find('div', class_='product-info').find_all('a')[1] if soup.find('div', class_='product-info') else None
                            if title_tag is None or price_tag is None:
                                log("SKipped " + book_url)
                                continue

                            title = title_tag.get_text().strip()
                            author = author_tag.get_text() if author_tag else None
                            isbn = isbn_tag.get_text().strip().replace("-", "") if isbn_tag else None
                            raw_p = price_tag.get_text().replace('LEI', '').replace(',', '.').strip()
                            price = float(raw_p.replace('.', '', 1) if raw_p.count('.') > 1 else raw_p)
                            category = self.map_category(category_tag.get_text().strip()) if category_tag else BookCategory.NONE

                            book = Book(
                                title=title,
                                author=author,
                                isbn=isbn,
                                category=category,
                                offers=[Offer(TARGUL_CARTII_NAME, book_url, price)]
                            )
                            self.add_book(book)
                        except Exception as e:
                            log(f"Caught {e}")
                except Exception as e:
                    log(f"Caught {e}")
        finally:
            self.destroy_scraper_thread()
