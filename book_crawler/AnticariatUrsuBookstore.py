# from book_crawler.bookstores.impl.core.BaseBookstore import BaseBookstore
#
# ANTICARIAT_URSU_BASE_URL = "https://anticariat-ursu.ro/"
# ANTICARIAT_URSU_NAME = "Anticariat Ursu"
# ANTICARIAT_URSU_PAGE_QUERY = "index.php?route=product/noutati&bfilter=s0:7;&limit=100&page=%s" # books only from last month
#
# class AnticariatUrsu(BaseBookstore):
#     def __init__(self):
#         base_address = "https://anticariat-ursu.ro"
#         name = "Anticariat Ursu"
#         page_query = "?bfilter=s0%3A7%3B&page=%s"
#         super().__init__(base_address, name, page_query)
#
#     def _getCategories(self):
#         request_result = makeRequest(self.base_address)
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#
#             categories = {}
#
#             main_categories = list(soup.find("ul", class_="list-unstyled").find_all("li", class_="sub_categorie"))
#             del main_categories[0]
#             del main_categories[0]
#             del main_categories[-1]
#             for cat in main_categories:
#                 for subcat in cat.find_all("a"):
#                     categories[subcat.get_text().strip()] = subcat.get('href').strip()
#
#             return categories
#
#     def getMaxPages(self, url):
#         request_result = makeRequest(url.replace("%s", "0"))
#         if request_result is not None:
#             page_html = request_result[1]
#             soup = BeautifulSoup(page_html, 'html.parser')
#             max_pages = soup.find("ul", class_="pagination").find_all("li")[-1].find("a").get("href")
#             max_pages = int(max_pages[max_pages.rfind("=") + 1:])
#             return max_pages
#
#     def getBookList(self, search_url, break_page):
#         self.current_page = 0
#         self.booklist = []
#         for _ in range(break_page):
#             request_result = makeRequest(search_url.replace("%s", str(self.current_page + 1)))
#             if request_result is not None:
#                 page_html = request_result[1]
#
#                 soup = BeautifulSoup(page_html, 'html.parser')
#
#                 divs_with_specific_class = soup.find_all('div',
#                                                          class_="product-layout product-grid col-lg-4 col-md-4 col-sm-6 col-xs-12 col-xss-12")
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
#             title_author_tag = soup.find('div', class_="col-sm-12").find('div', class_="row").find('h1')
#             isbn_tag = soup.find('li', string=re.compile(r'ISBN/COD:'))
#             price_tag = soup.find('span', id='price')
#
#             title_author = title_author_tag.get_text()
#             title = title_author[title_author.find("\"") + 1:1 + title_author.rfind("\"")]
#             title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
#             title = title[:title.lower().rfind("vol")]
#
#             author = re.search(r'scrisa de (.*)', title_author).group(1)
#             if "colectiv" in author.lower(): author = ""
#
#             isbn = isbn_tag.get_text(strip=True).split(':')[1].replace("-", '') if isbn_tag else ""
#             price = price_tag.get_text().replace("lei", '')
#
#             return Book(title, isbn, author, price, url)
