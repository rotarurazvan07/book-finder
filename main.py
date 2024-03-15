import re

from bs4 import BeautifulSoup

from main_window_ui import MainWindowApp
from utils import Book, Bookstore, makeRequest, log, getSimilarity

GOODREADS_SEARCH = "https://www.goodreads.com/search?q=%s"
PRINTRE_CARTI = "/istorie-si-geografie/istorie/?p=%s"
ANTICARIAT_UNU = "https://www.anticariat-unu.ro/istorie-c3/%s"
TARGUL_CARTII = "https://www.targulcartii.ro/istorie-si-etnografie?page=%s"
ANTICARIAT_URSU = "https://anticariat-ursu.ro/ISTORIE?page=%s"


# ANTIC_EXLIBRIS =


class PrintreCarti(Bookstore):
    def __init__(self):
        base_address = "https://www.printrecarti.ro"
        name = "Printre Carti"
        page_query = "?p=%s"
        super().__init__(base_address, name, page_query)
        self.categories = self._getCategories()

    def _getCategories(self):
        request_result = makeRequest(self.base_address)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            categories = {}

            categories_html = soup.find("li", class_="categorii primapagina")
            main_categories = categories_html.find_all("li", parinte=False)
            for category in main_categories:
                categories[category.find('a').get_text().strip()] = category.find('a').get('href').strip()
                sub_categories = category.find_all("li", parinte=True)
                for sub_category in sub_categories:
                    categories[sub_category.find('a').get_text().strip()] = sub_category.find('a').get('href').strip()

            return categories

    def getMaxPages(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            max_pages = soup.find("div", class_="nrpagc").find_all("span")[-1]
            max_pages = int(max_pages.find("a").get("href")[(max_pages.find("a").get("href").find("p=") + 2):]) \
                if max_pages.find("a") is not None else 1

            return max_pages

    def getBookList(self, search_url, break_page):
        self.current_page = 0
        self.booklist = []
        for _ in range(break_page):
            request_result = makeRequest(search_url % (self.current_page + 1))
            if request_result is not None:
                page_html = request_result[1]

                soup = BeautifulSoup(page_html, 'html.parser')

                divs_with_specific_class = soup.find_all('div', class_="produs ll")
                book_urls = set([a.get('href') for div in divs_with_specific_class for a in div.find_all('a')])

                for book_url in book_urls:
                    book = self._getBook(book_url)
                    book.rating = getRating(book)
                    self.booklist.append(book)
            self.current_page += 1
        return self.booklist

    def _getBook(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            title_tag = soup.find('titlu', itemprop='name')
            isbn_tag = soup.find('div', class_='divdescrieri').find(string=lambda text: 'ISBN' in text)
            author_tag = soup.find('autor', itemprop='author')
            try:
                price_tag = soup.find('div', class_='pret redus').find('pret', itemprop='price')
            except:
                price_tag = soup.find('div', class_='pret').find('pret', itemprop='price')

            title = title_tag.text.strip()
            isbn = isbn_tag.split(':')[-1].strip().replace("-", '') if isbn_tag else ""
            author = author_tag.text.strip() if author_tag else ""
            price = price_tag.text.strip()

            return Book(title, isbn, author, price, url)


class AnticariatUnu(Bookstore):
    def __init__(self):
        base_address = "https://www.anticariat-unu.ro"
        name = "Anticariat Unu"
        page_query = "/%s"
        super().__init__(base_address, name, page_query)
        self.categories = self._getCategories()

    def _getCategories(self):
        request_result = makeRequest(self.base_address)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            categories_html = soup.find("ul", class_="dropdown-menu show")
            categories_html = categories_html.find_all("li")
            categories_keys = [cat.get_text() for cat in categories_html]
            categories_urls = [cat.find('a').get('href') for cat in categories_html]
            categories = {k: v for k, v in zip(categories_keys, categories_urls)}

            return categories

    def getMaxPages(self, url):
        request_result = makeRequest(url % 0)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            max_pages = soup.find("li", class_="last").find("a").get("href")
            max_pages = int(max_pages[max_pages.rfind("/") + 1:])
            max_pages = int(max_pages / 30)

            return max_pages

    def getBookList(self, search_url, break_page):
        self.current_page = 0
        self.booklist = []
        for _ in range(break_page):
            request_result = makeRequest(search_url % (self.current_page * 30))
            if request_result is not None:
                page_html = request_result[1]

                soup = BeautifulSoup(page_html, 'html.parser')

                sections_with_specific_class = soup.find_all('section', class_="products-area")
                hrefs = [a.get('href') for div in sections_with_specific_class for a in div.find_all('a')]
                book_urls = set([href for href in hrefs if "javascript" not in href])

                for book_url in book_urls:
                    book = self._getBook(book_url)
                    if book is None:
                        return self.booklist
                    book.rating = getRating(book)
                    self.booklist.append(book)
            self.current_page += 1
        return self.booklist

    def _getBook(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            if "Stoc Epuizat" in page_html:  # early break condition, there is no filter for In stock
                return None
            soup = BeautifulSoup(page_html, 'html.parser')

            title_tag = soup.find('title')
            try:
                author_tag = soup.find(
                    lambda tag: tag.name == 'div' and tag.get_text(strip=True).startswith('Autor:')).find("div",
                                                                                                          class_="text")
            except:
                author_tag = None
            price_tag = soup.find('span', class_='price').find('span')

            title = title_tag.get_text()
            title = title[:-4]
            title = title.replace(",", "")
            if "..." in title: title = title[:title.find("...")]
            if " de " in title: title = title[:title.find(" de ") + 1]
            if " by " in title: title = title[:title.find(" by ") + 1]
            title = title.replace("  ", " ")
            title = title.strip()

            author = author_tag.get_text() if author_tag else ""
            if "..." in author: author = author[:author.find("...")]
            if " and " in author: author = author[:author.find(" and ") + 1]
            if " si " in author: author = author[:author.find(" si ") + 1]
            if "," in author: author = author[:author.find(",")]
            if "colectiv" in author.lower(): author = ""

            price = price_tag.text.strip()

            return Book(title, "", author, price, url)


class TargulCartii(Bookstore):
    def __init__(self):
        base_address = "https://www.targulcartii.ro"
        name = "Targul Cartii"
        page_query = "?page=%s"
        super().__init__(base_address, name, page_query)
        self.categories = self._getCategories()

    def _getCategories(self):
        request_result = makeRequest(self.base_address)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            categories_html = soup.find("ul", class_="mega-menu")
            categories_html = list(categories_html.find_all("li"))
            del categories_html[0]
            categories_keys = [cat.get_text() for cat in categories_html]
            categories_urls = [cat.find('a').get('href') for cat in categories_html]
            categories = {k: v for k, v in zip(categories_keys, categories_urls)}

            return categories

    def getMaxPages(self, url):
        request_result = makeRequest(url % 0)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')
            max_pages = int(soup.find("span", class_="pagination_total_pages").get_text())
            return max_pages

    def getBookList(self, search_url, break_page):
        self.current_page = 0
        self.booklist = []

        for _ in range(break_page):
            request_result = makeRequest(search_url % (self.current_page + 1))
            if request_result is not None:
                page_html = request_result[1]
                soup = BeautifulSoup(page_html, 'html.parser')

                divs_with_specific_class = soup.find_all('div', class_="detalii_btn")
                book_urls = set([a.get('href') for div in divs_with_specific_class for a in div.find_all('a')])

                for book_url in book_urls:
                    book = self._getBook(book_url)
                    book.rating = getRating(book)
                    self.booklist.append(book)
            self.current_page += 1
        return self.booklist

    def _getBook(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            title_tag = soup.find("h1", itemprop="name")
            author_tag = soup.find("span", itemprop="author")
            isbn_tag = soup.find("span", itemprop="isbn")
            price_tag = soup.find("span", class_="price-new")

            title = title_tag.get_text().strip()
            author = author_tag.get_text() if author_tag else ""
            isbn = isbn_tag.get_text().replace("-", "") if isbn_tag else ""
            price = price_tag.get_text().replace('LEI', '').strip()

            return Book(title, isbn, author, price, url)


class AnticariatUrsu(Bookstore):
    def __init__(self):
        base_address = "https://anticariat-ursu.ro"
        name = "Anticariat Ursu"
        page_query = "?bfilter=s0%3A7%3B&page=%s"
        super().__init__(base_address, name, page_query)
        self.categories = self._getCategories()

    def _getCategories(self):
        request_result = makeRequest(self.base_address)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            categories = {}

            main_categories = list(soup.find("ul", class_="list-unstyled").find_all("li", class_="sub_categorie"))
            del main_categories[0]
            del main_categories[0]
            del main_categories[-1]
            for cat in main_categories:
                for subcat in cat.find_all("a"):
                    categories[subcat.get_text().strip()] = subcat.get('href').strip()

            return categories

    def getMaxPages(self, url):
        request_result = makeRequest(url.replace("%s", "0"))
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')
            max_pages = soup.find("ul", class_="pagination").find_all("li")[-1].find("a").get("href")
            max_pages = int(max_pages[max_pages.rfind("=") + 1:])
            return max_pages

    def getBookList(self, search_url, break_page):
        self.current_page = 0
        self.booklist = []
        for _ in range(break_page):
            request_result = makeRequest(search_url.replace("%s", str(self.current_page + 1)))
            if request_result is not None:
                page_html = request_result[1]

                soup = BeautifulSoup(page_html, 'html.parser')

                divs_with_specific_class = soup.find_all('div',
                                                         class_="product-layout product-grid col-lg-4 col-md-4 col-sm-6 col-xs-12 col-xss-12")
                book_urls = set([a.get('href') for div in divs_with_specific_class for a in div.find_all('a')])

                for book_url in book_urls:
                    book = self._getBook(book_url)
                    book.rating = getRating(book)
                    self.booklist.append(book)
            self.current_page += 1
        return self.booklist

    def _getBook(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            title_author_tag = soup.find('div', class_="col-sm-12").find('div', class_="row").find('h1')
            isbn_tag = soup.find('li', string=re.compile(r'ISBN/COD:'))
            price_tag = soup.find('span', id='price')

            title_author = title_author_tag.get_text()
            title = title_author[title_author.find("\"") + 1:1 + title_author.rfind("\"")]
            title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
            title = title[:title.lower().rfind("vol")]

            author = re.search(r'scrisa de (.*)', title_author).group(1)
            if "colectiv" in author.lower(): author = ""

            isbn = isbn_tag.get_text(strip=True).split(':')[1].replace("-", '') if isbn_tag else ""
            price = price_tag.get_text().replace("lei", '')

            return Book(title, isbn, author, price, url)


class AnticExLibris(Bookstore):
    def __init__(self):
        name = "Antic ExLibris"
        base_address = "https://www.anticexlibris.ro"
        page_query = "?filter=-2/l/1&page=%s"
        super().__init__(base_address, name, page_query)

        self.categories = self._getCategories()

    def _getCategories(self):
        request_result = makeRequest(self.base_address)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            categories = {}

            categories_html = soup.find("div", id="megamenu")
            categories_html = list(categories_html.find("div", id="mm_slides").find_all("div", class_="mm_slide"))
            categories_html = categories_html[4:-5]
            for cat in categories_html:
                cats = cat.find_all("div", class_="title")
                if cats:
                    for sub_category in cats:
                        categories[sub_category.find('a').get_text().strip()] = self.base_address + sub_category.find(
                            'a').get("href").strip()
            categories["Erotica & Sexualitate"] = self.base_address + "/carti-despre-erotica-si-sexualitate-in-engleza"
            return categories

    def getMaxPages(self, url):
        request_result = makeRequest(url % 1)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')
            max_pages = soup.find_all("span", class_="filter_total")[1].get_text().strip()
            max_pages = re.sub(r'[^0-9\s]', '', max_pages)
            max_pages = int(int(max_pages) / 24) + 1
            return max_pages

    def getBookList(self, search_url, break_page):
        self.current_page = 0
        self.booklist = []
        for _ in range(break_page):
            request_result = makeRequest(search_url % (self.current_page + 1))
            if request_result is not None:
                page_html = request_result[1]
                soup = BeautifulSoup(page_html, 'html.parser')

                product_div = soup.find('div', class_="product_array_display product_grid_display")
                divs_with_specific_class = product_div.find_all('div', class_="__i")
                book_urls = set([a.get('href') for div in divs_with_specific_class for a in div.find_all('a')])

                for book_url in book_urls:
                    book = self._getBook(self.base_address + book_url)
                    book.rating = getRating(book)
                    self.booklist.append(book)
            self.current_page += 1
        return self.booklist

    def _getBook(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            title_tag = soup.find("div", id="product_title").find("div")
            isbn_tag = soup.find("div", id="ctl11_ctl00_product_ctl00_pnlCode")
            author_tag = soup.find("td", id="prv_17547")
            price_tag_int = soup.find("span", class_="money_expanded").find("span", class_="m_int")

            title = title_tag.get_text().strip()
            isbn = isbn_tag.get_text().replace("Cod", '').replace(":", '').strip()
            author = author_tag.get_text().strip() if author_tag else ""
            price = price_tag_int.get_text()

            return Book(title, isbn, author, price, url)


class Elefant(Bookstore):
    def __init__(self):
        name = "Elefant"
        base_address = "https://www.elefant.ro"
        page_query = "?pag=%s"
        super().__init__(base_address, name, page_query)

        self.categories = self._getCategories()

    def _getCategories(self):
        request_result = makeRequest(self.base_address + "/hp-carte")
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            categories = {}
            categories_html = soup.find("ul", id="discount_id", class_="filter-list clearfix collapse in")
            categories_html = categories_html.find_all("li", class_="filter-item")
            for cat in categories_html:
                categories[cat.find("a").get_text()] = self.base_address + cat.find("a").get("href")
            return categories

    def getMaxPages(self, url):
        request_result = makeRequest(url % 1)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')
            max_pages = soup.find("ul", class_="pagination-site-list").find_all("li")[-2].find("a").get("title")
            max_pages = int(max_pages[max_pages.rfind(" ")+1:])
            return max_pages

    def getBookList(self, search_url, break_page):
        self.current_page = 0
        self.booklist = []
        for _ in range(break_page):
            request_result = makeRequest(search_url % (self.current_page + 1))
            if request_result is not None:
                page_html = request_result[1]
                soup = BeautifulSoup(page_html, 'html.parser')

                divs_with_specific_class = soup.find_all('a', class_="product-title")
                book_urls = set([a.get('href') for a in divs_with_specific_class])

                for book_url in book_urls:
                    book = self._getBook(self.base_address + book_url)
                    book.rating = getRating(book)
                    self.booklist.append(book)
            self.current_page += 1
        return self.booklist

    def _getBook(self, url):
        request_result = makeRequest(url)
        if request_result is not None:
            page_html = request_result[1]
            soup = BeautifulSoup(page_html, 'html.parser')

            title_tag = soup.find("div", id="product_title").find("div")
            isbn_tag = soup.find("div", id="ctl11_ctl00_product_ctl00_pnlCode")
            author_tag = soup.find("td", id="prv_17547")
            price_tag_int = soup.find("span", class_="money_expanded").find("span", class_="m_int")

            title = title_tag.get_text().strip()
            isbn = isbn_tag.get_text().replace("Cod", '').replace(":", '').strip()
            author = author_tag.get_text().strip() if author_tag else ""
            price = price_tag_int.get_text()

            return Book(title, isbn, author, price, url)


def getRating(book):
    search_urls = [GOODREADS_SEARCH % book.isbn if book.isbn != "" else None,
                   GOODREADS_SEARCH % book.title.replace(" ", "%20"),
                   GOODREADS_SEARCH % (book.author + " " + book.title).replace(" ", "%20")]
    try:
        for search_url in [item for item in search_urls if item is not None]:
            request_result = makeRequest(search_url)
            if request_result is not None:
                page_html = request_result[1]
                if "Looking for a book?" not in page_html:
                    soup = BeautifulSoup(page_html, 'html.parser')
                    book_elements = soup.find_all('tr', itemtype='http://schema.org/Book')

                    # search ends up with list of books
                    if len(book_elements) > 0:
                        for book_elem in book_elements:
                            title = book_elem.find('a', class_='bookTitle').find('span', itemprop='name').get_text()
                            author = book_elem.find('a', class_='authorName').find('span',
                                                                                   itemprop='name').get_text()
                            web_title = book_elem.find('span', itemprop="name").get_text()
                            if "summary" not in title.lower():
                                if "colectiv" not in book.author.lower():
                                    similarity1 = getSimilarity(author, book.author)
                                    similarity2 = getSimilarity(web_title, book.author)
                                    if similarity1 < 0.2 and similarity2 < 0.2:
                                        continue
                                minirating_text = book_elem.find('span', class_='minirating').text.strip()
                                rating = re.search(r'(\d+\.\d+)', minirating_text).group(0)
                                ratings_count = re.search(r'(\d{1,3}(?:,\d{3})*) ratings?$', minirating_text).group(
                                    1).replace(",", '')
                                break
                    # search ended up on specific book page
                    else:
                        rating = soup.find('div', class_='RatingStatistics__rating').text.strip()
                        ratings_count_text = soup.find('span', {'data-testid': 'ratingsCount'}).text.strip()
                        ratings_count = re.search(r'\d{1,3}(?:,\d{3})*', ratings_count_text).group().replace(",", '')
            try:
                rating_score = float(rating) * float(ratings_count)
                log(f"Book found here, score: {rating_score}")
                return rating_score
            except UnboundLocalError as e:
                log(f"Book not found here")
    except Exception as e:
        log(f"An error occurred: {e}")

    return -1


if __name__ == '__main__':
    try:
        bookstores = [PrintreCarti(), AnticariatUnu(), TargulCartii(), AnticariatUrsu(), AnticExLibris(), Elefant()]
        app = MainWindowApp(bookstores)

        app.start()
    except Exception as e:
        print(f"Exception occurred: {e}")
