# import re

# from bs4 import BeautifulSoup

# from book_crawler.BaseBookstore import BaseBookstore
# from book_framework.core.Book import Book
# from book_framework.WebDriver import make_request
# from book_framework.utils import log

# ANTIC_EX_LIBRIS_BASE_URL = "https://www.anticexlibris.ro/"
# ANTIC_EX_LIBRIS_NAME = "Antic ExLibris"
# ANTIC_EX_LIBRIS_PAGE_QUERY = "produse-noi-carti-in-engleza?filter=-2/l/1&page=%s"

# class AnticExLibris(BaseBookstore):
#     def __init__(self, add_book_callback):
#         super().__init__(ANTIC_EX_LIBRIS_BASE_URL, ANTIC_EX_LIBRIS_NAME, ANTIC_EX_LIBRIS_PAGE_QUERY, add_book_callback)

#     def _getMaxPages(self):
#         request_result = make_request(self.url + self.page_query % "1")
#         if request_result is not None:
#             soup = BeautifulSoup(request_result, 'html.parser')
#             max_pages = soup.find_all("span", class_="filter_total")[1].get_text().strip()
#             max_pages = re.sub(r'[^0-9\s]', '', max_pages)
#             max_pages = int(int(max_pages) / 24) + 1
#             return max_pages

#     def get_books(self):
#         max_pages = self._getMaxPages()
#         for current_page in range(1, max_pages):
#             log(f"On page {current_page}")
#             request_result = make_request(self.url + self.page_query % current_page)
#             if request_result is not None:
#                 soup = BeautifulSoup(request_result, 'html.parser')

#                 product_div = soup.find('div', class_="product_array_display product_grid_display")
#                 divs_with_specific_class = product_div.find_all('div', class_="__i")
#                 book_urls = set([a.get('href') for div in divs_with_specific_class for a in div.find_all('a')])

#                 for book_url in book_urls:
#                     log(book_url)
#                     book = self._getBook(self.url + book_url)
#                     # don't add books without rating, its random stuff
#                     if book.rating == -1:
#                         continue
#                     self.add_book_callback(self.name, book)

#     def _getBook(self, url):
#         request_result = make_request(url)
#         if request_result is not None:
#             soup = BeautifulSoup(request_result, 'html.parser')

#             # TODO - DO LIKE THIS ON ALL OTHERS, CLEANER
#             title_tag = soup.find("div", id="product_title").find("div")
#             isbn_tag = soup.find("div", id="ctl11_ctl00_product_ctl00_pnlCode")
#             author_tag = soup.find("td", id="prv_17547")
#             price_tag_int = soup.find("div", class_="new_price").find("span", class_="m_int")
#             category_tag = soup.find('span', id="904672")

#             title = title_tag.get_text().strip()
#             isbn = isbn_tag.get_text().replace("Cod", '').replace(":", '').strip()
#             author = author_tag.get_text().strip() if author_tag else None
#             category = category_tag.get_text() if category_tag else None
#             price = int(price_tag_int.get_text()) + 1

#             return Book(title, isbn, author, price, category, url)
