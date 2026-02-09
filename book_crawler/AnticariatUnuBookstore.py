
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
ANTICARIAT_UNU_PAGE_QUERY = "/%s" # %s start from 0 and increments 30 by 30

NUM_THREADS = os.cpu_count()

class AnticariatUnu(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(add_book_callback)
        self._scanned_pages = 0
        self.cats = {
            BookCategory.LITERATURE: ["https://www.anticariat-unu.ro/autori-romani-c21",
                                      "https://www.anticariat-unu.ro/literatura-universala-autori-straini-c14",
                                     ],
            BookCategory.HISTORY: ["https://www.anticariat-unu.ro/istorie-c3",
                                   "https://www.anticariat-unu.ro/manuscrise-scrisori-documente-c58",
                                   "https://www.anticariat-unu.ro/ziare-reviste-publicatii-vechi-c52",
                                   "https://www.anticariat-unu.ro/manuale-vechi-c51",
                                   "https://www.anticariat-unu.ro/etnografie-folclor-c22",
                                   "https://www.anticariat-unu.ro/geografie-turism-geologie-astronomie-c19",
                                   ],
            BookCategory.ARTS: ["https://www.anticariat-unu.ro/arta-c4",
                                "https://www.anticariat-unu.ro/arhitectura-c13",
                                "https://www.anticariat-unu.ro/teatru-film-c16",
                                "https://www.anticariat-unu.ro/carti-muzica-c15",
                                ],
            BookCategory.SPIRITUALITY: ["https://www.anticariat-unu.ro/religie-c34",
                                        "https://www.anticariat-unu.ro/filosofie-logica-c17",
                                        "https://www.anticariat-unu.ro/pseudostiinte-ocultism-ezoterism-etc-c41",
                                        ],
            BookCategory.SCIENCE: ["https://www.anticariat-unu.ro/medicina-alopata-si-alternativa-c24",
                                   "https://www.anticariat-unu.ro/stiinte-juridice-c30",
                                   "https://www.anticariat-unu.ro/enciclopedii-carti-de-stiinta-c6",
                                   "https://www.anticariat-unu.ro/biologie-botanica-zoologie-c36",
                                   "https://www.anticariat-unu.ro/chimie-c39",
                                   "https://www.anticariat-unu.ro/matematica-fizica-c40",
                                   "https://www.anticariat-unu.ro/carti-tehnice-c29",
                                   ],
            BookCategory.BUSINESS: ["https://www.anticariat-unu.ro/stiinte-economice-management-si-marketing-c28"],
            BookCategory.PERSONAL_DEVELOPMENT: ["https://www.anticariat-unu.ro/psihologie-c18",
                                                "https://www.anticariat-unu.ro/sociologie-media-jurnalism-advertising-c31",
                                                "https://www.anticariat-unu.ro/pedagogie-c32"],
            BookCategory.KIDS_YA: ["https://www.anticariat-unu.ro/carti-pentru-copii-literatura-populara-benzi-desenate-c45"],
            BookCategory.HOBBIES: ["https://www.anticariat-unu.ro/gastronomie-c25",
                                   "https://www.anticariat-unu.ro/diverse-broderie-tricotaj-fotografie-etc-c37",
                                   "https://www.anticariat-unu.ro/educatie-fizica-sport-c44",
                                   "https://www.anticariat-unu.ro/pescuit-vanatoare-c42"],
        }

    def get_all_urls(self):
        self.get_web_scraper(profile='fast')
        urls = []
        for url in [url for urls in self.cats.values() for url in urls]:
            request_result = self.web_scraper.fast_http_request(url + ANTICARIAT_UNU_PAGE_QUERY % 0)
            soup = BeautifulSoup(request_result, 'html.parser')
            max_pages = (int(soup.find("li", class_="last").find('a')["data-ci-pagination-page"]) - 2)
            low = 0
            high = max_pages
            last_valid_page = 0
            while low <= high:
                mid = (low + high) // 2
                response_text = self.web_scraper.fast_http_request(url + (ANTICARIAT_UNU_PAGE_QUERY % (mid * 30)))
                if not response_text:
                    high = mid - 1
                    continue
                soup = BeautifulSoup(response_text, 'html.parser')
                sold_count = len([s for s in soup.select('span.text-danger') if s.get_text(strip=True) == "VANDUT"])
                if sold_count < 30:
                    last_valid_page = mid
                    low = mid + 1
                else:
                    high = mid - 1

            max_pages = last_valid_page
            for i in range(max_pages):
                urls.append(url + (ANTICARIAT_UNU_PAGE_QUERY % (i * 30)))
        self.destroy_scraper_thread()
        return urls

    def get_books(self, urls):
        self.get_web_scraper(profile='fast')
        self.run_workers(urls if urls is not None else self.get_all_urls(), self._find_books_job, num_threads=NUM_THREADS)
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
                    book_anchors = soup.find_all(class_="book")
                    for book_anchor in book_anchors:
                        try:
                            title_author_tag = book_anchor.find("h3").find("a")
                            book_url = title_author_tag['href']
                            price_tag = book_anchor.find(class_="price")
                            isbn_tag = None
                            if not title_author_tag or not price_tag:
                                continue # need at least title and price

                            title_author = title_author_tag.get_text().strip()
                            for separator in [" de ", " by ", " par ", "..."]:
                                if separator in title_author:
                                    title = title_author.rsplit(separator)[0]
                                    author = title_author.rsplit(separator)[1].split(",")[0]
                                    break
                                title = title_author
                                author = None
                            isbn = isbn_tag.get_text() if isbn_tag else None
                            price = float(price_tag.get_text().replace("Lei",'').strip())

                            book = Book(
                                title=title,
                                author=author,
                                isbn=isbn,
                                category = next((cat for cat, urls in self.cats.items() if any(u in url for u in urls)), BookCategory.NONE),
                                offers=[Offer(ANTICARIAT_UNU_NAME, book_url, price)]
                            )
                            self.add_book(book)
                        except Exception as e:
                            log(f"Caught {e}")
                except Exception as e:
                    log(f"Caught {e}")
        finally:
            self.destroy_scraper_thread()
