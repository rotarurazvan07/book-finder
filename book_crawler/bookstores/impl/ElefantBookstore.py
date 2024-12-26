# class Elefant(Bookstore):
#     def __init__(self):
#         name = "Elefant"
#         base_address = "https://www.elefant.ro"
#         page_query = "?pag=%s"
#         super().__init__(base_address, name, page_query)
#
#         self.categories = self._getCategories()
#
#     def _getCategories(self):
#         request_result = makeRequest(self.base_address + "/hp-carte")
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#
#             categories = {}
#             categories_html = soup.find("ul", id="discount_id", class_="filter-list clearfix collapse in")
#             categories_html = categories_html.find_all("li", class_="filter-item")
#             for cat in categories_html:
#                 categories[cat.find("a").get_text()] = self.base_address + cat.find("a").get("href")
#             return categories
#
#     def getMaxPages(self, url):
#         request_result = makeRequest(url % 1)
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#             max_pages = soup.find("ul", class_="pagination-site-list").find_all("li")[-2].find("a").get("title")
#             max_pages = int(max_pages[max_pages.rfind(" ")+1:])
#             return max_pages
#
#     def getBookList(self, search_url, break_page):
#         self.current_page = 0
#         self.booklist = []
#         for _ in range(break_page):
#             request_result = makeRequest(search_url % (self.current_page + 1))
#             if request_result is not None:
#                 page_html = request_result[1]
#                 soup = BeautifulSoup(page_html, 'html.parser')
#
#                 divs_with_specific_class = soup.find_all('a', class_="product-title")
#                 book_urls = set([a.get('href') for a in divs_with_specific_class])
#
#                 for book_url in book_urls:
#                     book = self._getBook(self.base_address + book_url)
#                     book.rating = getRating(book)
#                     self.booklist.append(book)
#             self.current_page += 1
#         return self.booklist
#
#     def _getBook(self, url):
#         request_result = makeRequest(url)
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#
#             title_tag = soup.find("div", id="product_title").find("div")
#             isbn_tag = soup.find("div", id="ctl11_ctl00_product_ctl00_pnlCode")
#             author_tag = soup.find("td", id="prv_17547")
#             price_tag_int = soup.find("span", class_="money_expanded").find("span", class_="m_int")
#
#             title = title_tag.get_text().strip()
#             isbn = isbn_tag.get_text().replace("Cod", '').replace(":", '').strip()
#             author = author_tag.get_text().strip() if author_tag else ""
#             price = price_tag_int.get_text()
#
#             return Book(title, isbn, author, price, url)
