# class PrintreCarti(Bookstore):
#     def __init__(self):
#         base_address = "https://www.printrecarti.ro"
#         name = "Printre Carti"
#         page_query = "?p=%s"
#         super().__init__(base_address, name, page_query)
#         self.categories = self._getCategories()
#
#     def _getCategories(self):
#         request_result = makeRequest(self.base_address)
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#
#             categories = {}
#
#             categories_html = soup.find("li", class_="categorii primapagina")
#             main_categories = categories_html.find_all("li", parinte=False)
#             for category in main_categories:
#                 categories[category.find('a').get_text().strip()] = category.find('a').get('href').strip()
#                 sub_categories = category.find_all("li", parinte=True)
#                 for sub_category in sub_categories:
#                     categories[sub_category.find('a').get_text().strip()] = sub_category.find('a').get('href').strip()
#
#             return categories
#
#     def getMaxPages(self, url):
#         request_result = makeRequest(url)
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#
#             max_pages = soup.find("div", class_="nrpagc").find_all("span")[-1]
#             max_pages = int(max_pages.find("a").get("href")[(max_pages.find("a").get("href").find("p=") + 2):]) \
#                 if max_pages.find("a") is not None else 1
#
#             return max_pages
#
#     def getBookList(self, search_url, break_page):
#         self.current_page = 0
#         self.booklist = []
#         for _ in range(break_page):
#             request_result = makeRequest(search_url % (self.current_page + 1))
#             if request_result is not None:
#                 page_html = request_result[1]
#
#                 soup = BeautifulSoup(page_html, 'html.parser')
#
#                 divs_with_specific_class = soup.find_all('div', class_="produs ll")
#                 book_urls = set([a.get('href') for div in divs_with_specific_class for a in div.find_all('a')])
#
#                 for book_url in book_urls:
#                     book = self._getBook(book_url)
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
#             title_tag = soup.find('titlu', itemprop='name')
#             isbn_tag = soup.find('div', class_='divdescrieri').find(string=lambda text: 'ISBN' in text)
#             author_tag = soup.find('autor', itemprop='author')
#             try:
#                 price_tag = soup.find('div', class_='pret redus').find('pret', itemprop='price')
#             except:
#                 price_tag = soup.find('div', class_='pret').find('pret', itemprop='price')
#
#             title = title_tag.text.strip()
#             isbn = isbn_tag.split(':')[-1].strip().replace("-", '') if isbn_tag else ""
#             author = author_tag.text.strip() if author_tag else ""
#             price = price_tag.text.strip()
#
#             return Book(title, isbn, author, price, url)
