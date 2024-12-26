from time import sleep

from bs4 import BeautifulSoup

from book_crawler.bookstores.impl.core.BaseBookstore import BaseBookstore
from book_crawler.bookstores.impl.core.Book import Book
from book_framework.WebDriver import make_request
from book_framework.utils import log

TARGUL_CARTII_BASE_URL = "https://www.targulcartii.ro/"
TARGUL_CARTII_NAME = "Targul Cartii"
TARGUL_CARTII_PAGE_QUERY = "noutati?limit=20&page=%s"

class TargulCartii(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(TARGUL_CARTII_BASE_URL, TARGUL_CARTII_NAME, TARGUL_CARTII_PAGE_QUERY, add_book_callback)

    def get_books(self):
        max_pages = self._getMaxPages()
        for current_page in range(1, max_pages):
            log(f"On page {current_page}")
            request_result = make_request(self.url + self.page_query % current_page)
            if request_result is None:
                print("Request problem, aborting")
                break

            html = BeautifulSoup(request_result, 'html.parser')

            book_urls = set([a.get('href') for div in html.find_all('div', class_="detalii_btn") for a in div.find_all('a')])
            for book_url in book_urls:
                log(book_url)
                book = self._getBook(book_url)
                if book is None:
                    continue
                # don't add books without rating, its random stuff
                if book.rating == -1:
                    continue
                self.add_book_callback(self.name, book)


    def _getMaxPages(self):
        request_result = make_request(self.url + self.page_query % "0")
        if request_result is not None:
            soup = BeautifulSoup(request_result, 'html.parser')
            max_pages = int(soup.find("span", class_="pagination_total_pages").get_text())
            return max_pages

    def _getBook(self, url):
        request_result = make_request(url)
        if "STOC EPUIZAT!" in request_result:
            return None
        if request_result is not None:
            soup = BeautifulSoup(request_result, 'html.parser')

            title_tag = soup.find("h1", itemprop="name")
            author_tag = soup.find("span", itemprop="author")
            isbn_tag = soup.find("span", itemprop="isbn")
            price_tag = soup.find("span", class_="price-new")

            title = title_tag.get_text().strip()
            author = author_tag.get_text() if author_tag else None
            isbn = isbn_tag.get_text().replace("-", "") if isbn_tag else None
            price = price_tag.get_text().replace('LEI', '').strip()

            category = soup.find('div', class_='product-info').find_all('span', itemprop='itemListElement')[-2].find('a').find('span').get_text()
            return Book(title, isbn, author, price, category, url)
