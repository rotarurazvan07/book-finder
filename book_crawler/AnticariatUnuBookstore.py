
import re
from time import sleep

from bs4 import BeautifulSoup
import os
import time
from book_crawler.BaseBookstore import BaseBookstore
from book_framework.core.Book import Book, Offer,BookCategory
from book_framework.utils import log

ANTICARIAT_UNU_BASE_URL = "https://www.anticariat-unu.ro/"
ANTICARIAT_UNU_NAME = "Anticariat Unu"
ANTICARIAT_UNU_PAGE_QUERY = "carti-c1/%s" # %s start from 0 and increments 30 by 30

NUM_THREADS = os.cpu_count()

class AnticariatUnu(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(add_book_callback)
        self._scanned_pages = 0

    @property
    def category_map(self) -> dict:
        return {
            # --- LITERATURE ---
            "Autori romani": BookCategory.LITERATURE,
            "Literatura universala / Autori Straini": BookCategory.LITERATURE,
            "Critica literara / Lingvistica / Gramatica limbii romane / Istoria literaturii": BookCategory.LITERATURE,
            "Carti cu dedicatie, semnate": BookCategory.LITERATURE,
            "Limbi Straine ( gramatica, dictionare, cursuri etc.)": BookCategory.LITERATURE,

            # --- HISTORY ---
            "Istorie": BookCategory.HISTORY,
            "Bibliofilie": BookCategory.HISTORY,
            "Editii princeps": BookCategory.HISTORY,
            "Manuscrise / Scrisori / Documente": BookCategory.HISTORY,
            "Carte veche": BookCategory.HISTORY,
            "Ziare / Reviste / Publicatii vechi": BookCategory.HISTORY,
            "Manuale vechi": BookCategory.HISTORY,
            "Etnografie & Folclor": BookCategory.HISTORY,
            "Geografie / Turism / Geologie / Astronomie": BookCategory.HISTORY,

            # --- ARTS ---
            "Arta": BookCategory.ARTS,
            "Arhitectura": BookCategory.ARTS,
            "Teatru & Film": BookCategory.ARTS,
            "Carti Muzica": BookCategory.ARTS,

            # --- SPIRITUALITY ---
            "Religie": BookCategory.SPIRITUALITY,
            "Filosofie / Logica": BookCategory.SPIRITUALITY,
            "Pseudostiinte (Ocultism, Ezoterism etc.)": BookCategory.SPIRITUALITY,

            # --- SCIENCE ---
            "Medicina alopata si alternativa": BookCategory.SCIENCE,
            "Stiinte juridice": BookCategory.SCIENCE,
            "Enciclopedii & Carti de stiinta": BookCategory.SCIENCE,
            "Biologie / Botanica / Zoologie": BookCategory.SCIENCE,
            "Chimie": BookCategory.SCIENCE,
            "Matematica / Fizica": BookCategory.SCIENCE,
            "Carti Tehnice": BookCategory.SCIENCE,

            # --- BUSINESS ---
            "Stiinte economice / Management si Marketing": BookCategory.BUSINESS,

            # --- PERSONAL DEVELOPMENT ---
            "Psihologie": BookCategory.PERSONAL_DEVELOPMENT,
            "Sociologie / Media / Jurnalism / Advertising": BookCategory.PERSONAL_DEVELOPMENT,
            "Pedagogie": BookCategory.PERSONAL_DEVELOPMENT,

            # --- KIDS & YA ---
            "Carti pentru copii/ Literatura populara / Benzi desenate": BookCategory.KIDS_YA,

            # --- HOBBIES ---
            "Gastronomie": BookCategory.HOBBIES,
            "Diverse (Broderie, Tricotaj, Fotografie, etc.)": BookCategory.HOBBIES,
            "Educatie fizica & Sport": BookCategory.HOBBIES,
            "Pescuit & Vanatoare": BookCategory.HOBBIES,

            # --- OTHER / NONE ---
            "Diverse": BookCategory.OTHER
        }

    def get_books(self):
        # Build urls to scrape
        self.get_web_scraper(profile='fast')
        html = self.web_scraper.fast_http_request(ANTICARIAT_UNU_BASE_URL + ANTICARIAT_UNU_PAGE_QUERY % 30)
        soup = BeautifulSoup(html, 'html.parser')
        max_pages = (int(soup.find("li", class_="last").find('a')["data-ci-pagination-page"]) - 2)
        # go from back to start and find whats the last real page
        low = 0
        high = max_pages
        last_valid_page = 0

        while low <= high:
            mid = (low + high) // 2
            url = ANTICARIAT_UNU_BASE_URL + (ANTICARIAT_UNU_PAGE_QUERY % (mid * 30))

            response_text = self.web_scraper.fast_http_request(url)
            if not response_text:
                # If request fails, treat as "sold" to be safe, or handle error
                high = mid - 1
                continue

            soup = BeautifulSoup(response_text, 'html.parser')
            sold_count = len([s for s in soup.select('span.text-danger') if s.get_text(strip=True) == "VANDUT"])

            if sold_count < 30:
                # This page has live books! The "last" page might be even further right.
                last_valid_page = mid
                low = mid + 1
            else:
                # This page is 100% sold out. Move left to find where inventory starts.
                high = mid - 1

        max_pages = last_valid_page
        log(f"Max page index: {max_pages}")
        self.destroy_scraper_thread()

        # Get all URLs
        urls = [ANTICARIAT_UNU_BASE_URL + (ANTICARIAT_UNU_PAGE_QUERY % (i * 30)) for i in range(max_pages)]

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

                request_result = self.web_scraper.fast_http_request(url)
                try:
                    soup = BeautifulSoup(request_result, 'html.parser')
                    hrefs = [a.get('href') for div in soup.find_all('section', class_="products-area") for a in div.find_all('a')]
                    book_urls = set([href for href in hrefs if "javascript" not in href])
                    for book_url in book_urls:
                        request_result = self.web_scraper.fast_http_request(book_url)
                        try:
                            if "Stoc Epuizat" in request_result or "anunta-ma cand este disponibil produsul" in request_result:
                                continue
                            soup = BeautifulSoup(request_result, 'html.parser')

                            title_tag = soup.find('title')
                            author_tag = soup.find('div', string="Autor:").find_next_sibling('div', class_='text') if soup.find('div', string="Autor:") else None
                            price_tag = soup.find('span', class_='price').find('span')
                            category_tag = soup.find('div', class_='breadcrumbs').find_all('li')[-1]
                            if title_tag is None or price_tag is None:
                                log("SKipped " + book_url)
                                continue

                            title = title_tag.get_text()
                            title = title[:-4]
                            title = title.replace(",", "")
                            for separator in ["...", " de ", " by "]:
                                if separator in title:
                                    title = title.split(separator)[0]
                            title = title.replace("  ", " ")
                            title = title.strip()

                            author = author_tag.get_text() if author_tag else None
                            if author:
                                if "colectiv" in author.lower():
                                    author = None
                                else:
                                    for sep in ["...", " and ", " si ", ","]:
                                        if sep in author:
                                            author = author.split(sep)[0]
                                    author = author.strip()

                            price = float(price_tag.text.strip())
                            category = self.map_category(category_tag.get_text().strip()) if category_tag else BookCategory.NONE
                            isbn = None # doesn't exist on this bookstore
                            book = Book(
                                title=title,
                                author=author,
                                isbn=isbn,
                                category=category,
                                offers=[Offer(ANTICARIAT_UNU_NAME, book_url, price)]
                            )
                            self.add_book(book)
                        except Exception as e:
                            log(f"Caught {e}")
                except Exception as e:
                    log(f"Caught {e}")
        finally:
            self.destroy_scraper_thread()
