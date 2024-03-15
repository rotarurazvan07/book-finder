
import re
from bs4 import BeautifulSoup
from book_framework.utils import log
from book_framework.WebScraper import WebScraper
from book_framework.SimilarityEngine import SimilarityEngine
import threading
from math import ceil

GOODREADS_URL = "https://www.goodreads.com/"
GOODREADS_SEARCH = GOODREADS_URL + "search?q=%s"

NOT_FOUND_INDICATOR = "looking for a book?"
REJECTED_GOODREADS_TITLES = ["summary"]

def rateBooks(books_df, callback, num_threads=5):
    # 1. Use standard slicing (works on DataFrames)
    total_rows = len(books_df)
    chunk_size = ceil(total_rows / num_threads)
    similarity_engine = SimilarityEngine()

    threads = []

    def thread_worker(df_chunk):
        web_scraper = WebScraper()
        for book in df_chunk.itertuples(index=False):
            rating, goodreads_url = getRating(book, web_scraper, similarity_engine)
            callback(book.rowid, rating, goodreads_url)
        web_scraper.destroy_current_thread()

    # 3. Create chunks and start threads
    for i in range(0, total_rows, chunk_size):
        chunk = books_df.iloc[i : i + chunk_size] # Use .iloc for safe DF slicing

        t = threading.Thread(target=thread_worker, args=(chunk,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    del similarity_engine

def getRating(book, web_scraper, similarity_engine):
    rating = None

    # Use dot notation for NamedTuples
    title = book.title
    author = getattr(book, 'author', None) # Safely get if column might be missing
    isbn = getattr(book, 'isbn', None)

    log(f"Finding rating for {title}")

    # 1. ISBN attempt - HIT goes directly to book page
    if isbn:
        request_result = web_scraper.fast_http_request(GOODREADS_SEARCH % isbn)
        try:
            if request_result is not None:
                if NOT_FOUND_INDICATOR not in request_result.lower(): # even if we have isbn, not guaranteed to exist
                    log(f"ISBN hit: {isbn}")
                    html = BeautifulSoup(request_result, 'html.parser')

                    # TODO: chance to update missing book data also

                    rating = html.find('div', class_='RatingStatistics__rating').text.strip()
                    ratings_count_text = html.find('span', {'data-testid': 'ratingsCount'}).text.strip()
                    ratings_count = re.search(r'\d{1,3}(?:,\d{3})*', ratings_count_text).group().replace(",",'')

                    return float(rating) * float(ratings_count), GOODREADS_SEARCH % isbn
        except Exception as e:
            log(f"Caught {e}")

    #2. Author and title searches, these go in the search page that gives a list
    search_urls = []
    if author:
        combined_query = f"{author} {title}".replace(" ", "%20")
        search_urls.append(GOODREADS_SEARCH % combined_query)
    title_query = title.replace(" ", "%20")
    search_urls.append(GOODREADS_SEARCH % title_query)

    for search_url in search_urls:
        request_result = web_scraper.fast_http_request(search_url)
        try:
            if request_result is not None:
                if NOT_FOUND_INDICATOR not in request_result.lower():
                    html = BeautifulSoup(request_result, 'html.parser')
                    # this is the list of books goodreads shows when searching
                    book_elements = html.find_all('tr', itemtype='http://schema.org/Book')
                    for book_elem in book_elements:
                        goodreads_title = book_elem.find('a', class_='bookTitle').find('span', itemprop='name').get_text()
                        goodreads_author = book_elem.find('a', class_='authorName').find('span', itemprop='name').get_text()
                        web_title = book_elem.find('span', itemprop="name").get_text()
                        log(f"Trying {goodreads_author} + {goodreads_title}")
                        # skip titles that are summaries, etc
                        if goodreads_title.lower() in REJECTED_GOODREADS_TITLES:
                            continue

                        match = similarity_engine.is_similar(title, goodreads_title)
                        if match is True and author is not None and goodreads_author is not None:
                            match = similarity_engine.is_similar(author, goodreads_author)

                        if match:
                            log(f"Book hit: {web_title}")
                            # TODO: chance to update missing book data also
                            minirating_text = book_elem.find('span', class_='minirating').text.strip()
                            rating = re.search(r'(\d+\.\d+)', minirating_text).group(0)
                            ratings_count = re.search(r'(\d{1,3}(?:,\d{3})*) ratings?$', minirating_text).group(1).replace(",", '')
                            return float(rating) * float(ratings_count), GOODREADS_URL + book_elem.find('a')['href']
        except Exception as e:
            log(f"Caught {e}")
    log(f"Couldn't find rating on goodreads for {title}")
    return None, None
