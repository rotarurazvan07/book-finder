import re
from statistics import mean

from bs4 import BeautifulSoup

from book_framework.WebDriver import make_request
from book_framework.utils import log, getSimilarity

GOODREADS_URL = "https://www.goodreads.com/"
GOODREADS_SEARCH = GOODREADS_URL + "search?q=%s"

NOT_FOUND_INDICATOR = "looking for a book?"
REJECTED_GOODREADS_TITLES = ["summary"]

SIMILARITY_THRESHOLD = 75
NO_RATING = -1

class Book:
    def __init__(self, title, isbn, author, price, category, url, rating=None, goodreads_url=None):
        self.title = title
        self.isbn = isbn
        self.author = author
        self.price = price
        self.category = category
        self.url = url
        if rating is not None and goodreads_url is not None:
            self.rating = rating
            self.goodreads_url = goodreads_url
        else:
            self.rating, self.goodreads_url = self.getRatingV2()

    def getRatingV2(self):
        log(f"Finding rating for {self.author} + {self.title}")

        # GOODREADS can directly point you to the book if you know the isbn, so try that first
        if self.isbn is not None:
            # we have isbn
            request_result = make_request(GOODREADS_SEARCH % self.isbn)
            if request_result is not None:
                if NOT_FOUND_INDICATOR not in request_result.lower(): # even if we have isbn, not guaranteed to exist
                    log(f"ISBN hit: {self.isbn}")
                    html = BeautifulSoup(request_result, 'html.parser')
                    if self.author is None:
                        self.author = html.find("span", class_='ContributorLink__name').get_text()
                    if self.category is None:
                        category_tag = html.find('div', class_="BookPageMetadataSection__genres")
                        self.category = category_tag.find('a', class_="Button Button--tag Button--medium").find('span').get_text() if category_tag else None
                    rating = html.find('div', class_='RatingStatistics__rating').text.strip()
                    ratings_count_text = html.find('span', {'data-testid': 'ratingsCount'}).text.strip()
                    ratings_count = re.search(r'\d{1,3}(?:,\d{3})*', ratings_count_text).group().replace(",",'')
                    return float(rating) * float(ratings_count), GOODREADS_SEARCH % self.isbn

        # if at this point we didn't return, means we don't have isbn
        # try the title and author+title combination
        search_urls = [GOODREADS_SEARCH % self.title.replace(" ", "%20")]
        if self.author is not None: # sometimes author is a collective and it is useless to search with it
            search_urls.append(GOODREADS_SEARCH % (self.author + " " + self.title).replace(" ", "%20"))

        for search_url in search_urls:
            request_result = make_request(search_url)
            if request_result is not None:
                if NOT_FOUND_INDICATOR not in request_result.lower():
                    html = BeautifulSoup(request_result, 'html.parser')
                    # this is the list of books goodreads shows when searching
                    book_elements = html.find_all('tr', itemtype='http://schema.org/Book')
                    for book_elem in book_elements:
                        title = book_elem.find('a', class_='bookTitle').find('span', itemprop='name').get_text()
                        author = book_elem.find('a', class_='authorName').find('span', itemprop='name').get_text()
                        web_title = book_elem.find('span', itemprop="name").get_text()
                        log(f"Trying {author} + {title}")
                        # skip titles that are summaries, etc
                        if title.lower() in REJECTED_GOODREADS_TITLES:
                            continue

                        # now get similarities
                        similarities = dict()
                        if self.author: # not always we have author
                            similarities["author"] = (getSimilarity(self.author, author))
                        similarities["title"] = (getSimilarity(self.title, title))

                        if (mean(similarities.values()) > SIMILARITY_THRESHOLD or
                           similarities["title"] > SIMILARITY_THRESHOLD):
                            log("Book hit here")
                            if self.isbn is None:
                                pass
                            if self.author is None:
                                self.author = author
                            if self.category is None:
                                pass
                            # we found the book
                            minirating_text = book_elem.find('span', class_='minirating').text.strip()
                            rating = re.search(r'(\d+\.\d+)', minirating_text).group(0)
                            ratings_count = re.search(r'(\d{1,3}(?:,\d{3})*) ratings?$', minirating_text).group(1).replace(",", '')
                            return float(rating) * float(ratings_count), GOODREADS_URL + book_elem.find('a')['href']

        log(f"Couldn't find rating on goodreads")
        return NO_RATING, None


    def getRating(self):
        search_urls = [GOODREADS_SEARCH % self.isbn if self.isbn != "" else None,
                       GOODREADS_SEARCH % self.title.replace(" ", "%20"),
                       GOODREADS_SEARCH % (self.author + " " + self.title).replace(" ", "%20")]
        try:
            for search_url in [item for item in search_urls if item is not None]:
                request_result = make_request(search_url)
                if request_result is not None:
                    if "Looking for a book?" not in request_result:
                        soup = BeautifulSoup(request_result, 'html.parser')
                        book_elements = soup.find_all('tr', itemtype='http://schema.org/Book')

                        # TODO search ends up with list of books
                        if len(book_elements) > 0:
                            for book_elem in book_elements:
                                title = book_elem.find('a', class_='bookTitle').find('span', itemprop='name').get_text()
                                author = book_elem.find('a', class_='authorName').find('span',
                                                                                       itemprop='name').get_text()
                                web_title = book_elem.find('span', itemprop="name").get_text()
                                if "summary" not in title.lower():
                                    if "colectiv" not in self.author.lower():
                                        similarity1 = getSimilarity(author, self.author)
                                        similarity2 = getSimilarity(web_title, self.author)
                                        if similarity1 < 80 and similarity2 < 80:
                                            continue
                                    minirating_text = book_elem.find('span', class_='minirating').text.strip()
                                    rating = re.search(r'(\d+\.\d+)', minirating_text).group(0)
                                    ratings_count = re.search(r'(\d{1,3}(?:,\d{3})*) ratings?$', minirating_text).group(
                                        1).replace(",", '')
                                    break
                        # TODO search ended up on specific book page
                        else:
                            rating = soup.find('div', class_='RatingStatistics__rating').text.strip()
                            ratings_count_text = soup.find('span', {'data-testid': 'ratingsCount'}).text.strip()
                            ratings_count = re.search(r'\d{1,3}(?:,\d{3})*', ratings_count_text).group().replace(",",
                                                                                                                 '')
                try:
                    rating_score = float(rating) * float(ratings_count)
                    log(f"Book found here, score: {rating_score}")
                    return rating_score
                except UnboundLocalError as e:
                    log(f"Book not found here")
        except Exception as e:
            log(f"An error occurred: {e}")

        return -1