import re
from time import sleep

from bs4 import BeautifulSoup
import os
import time
from book_crawler.BaseBookstore import BaseBookstore
from book_framework.core.Book import Book, Offer,BookCategory
from book_framework.utils import log

PRINTRE_CARTI_BASE_URL = "https://www.printrecarti.ro/"
PRINTRE_CARTI_NAME = "Printre carti"
PRINTRE_CARTI_PAGE_QUERY = "?p=%s"

NUM_THREADS = os.cpu_count()

class PrintreCarti(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(add_book_callback)
        self._scanned_pages = 0

    @property
    def category_map(self) -> dict:
        return {
            "Literatura si critica": BookCategory.LITERATURE,
            "Dictionare si Limbi straine": BookCategory.LITERATURE, # Usually reference or foreign fiction
            "Arta si Albume": BookCategory.ARTS,
            "Psihologie. Dezvoltare personala": BookCategory.PERSONAL_DEVELOPMENT,
            "Stiinte umaniste": BookCategory.SCIENCE,            # Sociology, philosophy, etc.
            "Stiinte": BookCategory.SCIENCE,                     # Pure sciences
            "Istorie si Geografie": BookCategory.HISTORY,
            "Carte Veche. Bibliofilie": BookCategory.HISTORY,    # Historical value/Archive
            "Spiritualitate si Religie": BookCategory.SPIRITUALITY,
            "Diverse": BookCategory.OTHER
        }

    def get_books(self):
        # Build urls to scrape
        urls = []
        self.get_web_scraper(profile='slow')
        html = self.web_scraper.fast_http_request(PRINTRE_CARTI_BASE_URL)
        if html is not None:
            soup = BeautifulSoup(html, 'html.parser')
            categories_html = soup.find("li", class_="categorii primapagina").find_all("li", parinte=False)
            categories_urls = [cat.find('a')['href'] for cat in categories_html]
            for category_url in categories_urls:
                html = self.web_scraper.fast_http_request(category_url)
                if html is not None:
                    soup = BeautifulSoup(html, 'html.parser')

                    max_pages = soup.find("div", class_="nrpagc").find_all("span")[-1]
                    max_pages = int(max_pages.find("a").get("href")[(max_pages.find("a").get("href").find("p=") + 2):]) \
                        if max_pages.find("a") is not None else 1

                    urls += [(category_url + PRINTRE_CARTI_PAGE_QUERY) % i for i in range(1, max_pages + 1)]
        self.destroy_scraper_thread()

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
                html = self.web_scraper.fast_http_request(url)
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    book_urls = set([a.get('href') for div in soup.find_all('div', class_="produs ll") for a in div.find_all('a')])
                    for book_url in book_urls:

                        html = self.web_scraper.fast_http_request(book_url)
                        try:
                            if "STOC EPUIZAT!" in html:
                                continue

                            soup = BeautifulSoup(html, 'html.parser')

                            title_tag = soup.find('titlu', itemprop='name')
                            isbn_tag = soup.find('div', class_='divdescrieri').find(string=lambda text: 'ISBN' in text)
                            author_tag = soup.find('autor', itemprop='author')
                            if soup.find('div', class_='pret redus'):
                                price_tag = soup.find('div', class_='pret redus').find('pret', itemprop='price')
                            elif soup.find('div', class_='pret'):
                                price_tag = soup.find('div', class_='pret').find('pret', itemprop='price')
                            if title_tag is None or price_tag is None:
                                log("SKipped " + book_url)
                                continue

                            title = title_tag.text.strip()
                            isbn = isbn_tag.split(':')[-1].strip().replace("-", '') if isbn_tag else None
                            author = author_tag.text.strip() if author_tag else None
                            price = float(price_tag.text.replace(",",".").strip())
                            category_match = re.search(r'#calemagazin"\)\.html\(.*?href=\\".*?\\">.*?</a> » <a href=\\".*?\\">(.*?)</a>', html)
                            raw_cat = category_match.group(1) if category_match else None
                            category = self.map_category(raw_cat) if category_match else BookCategory.NONE

                            book = Book(
                                title=title,
                                author=author,
                                isbn=isbn,
                                category=category,
                                offers=[Offer(PRINTRE_CARTI_NAME, book_url, price)]
                            )
                            self.add_book(book)
                        except Exception as e:
                            log(f"Caught {e}")
                except Exception as e:
                    log(f"Caught {e}")
        finally:
            self.destroy_scraper_thread()
