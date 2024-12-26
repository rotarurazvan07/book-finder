from bs4 import BeautifulSoup

from book_framework.WebDriver import make_request
from book_crawler.bookstores.impl.core.BaseBookstore import BaseBookstore
from book_crawler.bookstores.impl.core.Book import Book
from book_framework.utils import log

ANTICARIAT_UNU_BASE_URL = "https://www.anticariat-unu.ro/"
ANTICARIAT_UNU_NAME = "Anticariat Unu"
ANTICARIAT_UNU_PAGE_QUERY = "carti-c1/%s" # %s start from 0 and increments 30 by 30

class AnticariatUnu(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(ANTICARIAT_UNU_BASE_URL, ANTICARIAT_UNU_NAME, ANTICARIAT_UNU_PAGE_QUERY, add_book_callback)

    def get_books(self):
        # Go over all the books, in order to save them in mongo DB
        current_page = 0
        while True:
            log(f"On page {current_page}")
            request_result = make_request(self.url + (self.page_query % (current_page * 30)))
            if request_result is None:
                print("Request problem, aborting")
                break
            html = BeautifulSoup(request_result, 'html.parser')
            # find all books urls from current page
            hrefs = [a.get('href') for div in html.find_all('section', class_="products-area") for a in div.find_all('a')]
            book_urls = set([href for href in hrefs if "javascript" not in href])
            # iterate over all books and call the callback
            for book_url in book_urls:
                log(book_url)
                book = self._getBook(book_url)
                if book is None: # break condition
                    return # finish function
                # don't add books without rating, its random stuff
                if book.rating == -1:
                    continue
                self.add_book_callback(self.name, book)
            current_page += 1

    def _getBook(self, url):
        request_result = make_request(url)
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')
            if "Stoc Epuizat" in html:  # early break condition, there is no filter for In stock
                return None

            title_tag = html.find('title')
            try:
                author_tag = html.find(
                    lambda tag: tag.name == 'div' and tag.get_text(strip=True).startswith('Autor:')).find("div",
                                                                                                          class_="text")
            except:
                author_tag = None
            price_tag = html.find('span', class_='price').find('span')

            title = title_tag.get_text()
            title = title[:-4]
            title = title.replace(",", "")
            if "..." in title: title = title[:title.find("...")]
            if " de " in title: title = title[:title.find(" de ") + 1]
            if " by " in title: title = title[:title.find(" by ") + 1]
            title = title.replace("  ", " ")
            title = title.strip()

            author = author_tag.get_text() if author_tag else None
            if "..." in author: author = author[:author.find("...")]
            if " and " in author: author = author[:author.find(" and ") + 1]
            if " si " in author: author = author[:author.find(" si ") + 1]
            if "," in author: author = author[:author.find(",")]
            if "colectiv" in author.lower(): author = None

            price = price_tag.text.strip()

            category = html.find('div', class_='breadcrumbs').find_all('li')[-1].get_text().strip()
            isbn = None # doesn't exist on this bookstore

            return Book(title, isbn, author, price, category, url)
