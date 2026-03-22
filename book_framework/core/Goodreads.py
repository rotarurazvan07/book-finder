import os
import re
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor

from book_framework.utils import log
from book_framework.WebScraper import WebScraper
from book_framework.SimilarityEngine import SimilarityEngine

# Constants for Goodreads integration
GOODREADS_URL = "https://www.goodreads.com/"
GOODREADS_SEARCH = GOODREADS_URL + "search?q=%s"
NOT_FOUND_INDICATOR = "looking for a book?"
REJECTED_GOODREADS_TITLES = ["summary", "review", "preview"]

def getRating(book, similarity_engine: SimilarityEngine) -> Tuple[Optional[float], Optional[str]]:
    """Searches Goodreads for a book's total weighted rating (rating * count).
    Attempts search by ISBN first, then by author/title combination.
    """
    title = book.title
    author = getattr(book, 'author', None)
    isbn = getattr(book, 'isbn', None)

    log(f"Finding rating for {title}")

    # 1. Primary Attempt: ISBN
    if isbn:
        try:
            search_url = GOODREADS_SEARCH % isbn
            request_result = WebScraper.fetch(search_url, stealthy_headers=True)
            if request_result and NOT_FOUND_INDICATOR not in request_result.lower():
                log(f"ISBN hit: {isbn}")
                html = BeautifulSoup(request_result, 'html.parser')
                rating_val = html.find('div', class_='RatingStatistics__rating').text.strip()
                ratings_count_text = html.find('span', {'data-testid': 'ratingsCount'}).text.strip()

                # Extract numeric count, handling thousand separators
                match = re.search(r'\d{1,3}(?:,\d{3})*', ratings_count_text)
                if match:
                    ratings_count = match.group().replace(",", "")
                    return float(rating_val) * float(ratings_count), search_url
        except (AttributeError, ValueError, TypeError) as e:
            log(f"ISBN parse error for {isbn}: {e}")

    # 2. Secondary Attempt: Title and Author searches
    search_queries = []
    if author:
        search_queries.append(f"{author} {title}")
    search_queries.append(title)

    for query in search_queries:
        try:
            search_url = GOODREADS_SEARCH % query.replace(" ", "%20")
            request_result = WebScraper.fetch(search_url, stealthy_headers=True)

            if not request_result or NOT_FOUND_INDICATOR in request_result.lower():
                continue

            html = BeautifulSoup(request_result, 'html.parser')
            book_elements = html.find_all('tr', itemtype='http://schema.org/Book')

            for book_elem in book_elements:
                gr_title = book_elem.find('a', class_='bookTitle').find('span', itemprop='name').get_text()
                gr_author = book_elem.find('a', class_='authorName').find('span', itemprop='name').get_text()

                if gr_title.lower() in REJECTED_GOODREADS_TITLES:
                    continue

                # Title match is required
                matched, _ = similarity_engine.is_similar(title, gr_title)

                # Author match is secondary validation
                if matched and author and gr_author:
                    matched, _ = similarity_engine.is_similar(author, gr_author)

                if matched:
                    # Extract rating and count from 'minirating' block: e.g. "4.21 avg rating — 1,234 ratings"
                    minirating_text = book_elem.find('span', class_='minirating').text.strip()
                    rating_match = re.search(r'(\d+\.\d+)', minirating_text)
                    count_match = re.search(r'(\d{1,3}(?:,\d{3})*) ratings?$', minirating_text)

                    if rating_match and count_match:
                        rating_val = rating_match.group(1)
                        ratings_count = count_match.group(1).replace(",", "")
                        book_path = book_elem.find('a')['href']
                        return float(rating_val) * float(ratings_count), GOODREADS_URL + book_path

        except (AttributeError, ValueError, TypeError, KeyError) as e:
            log(f"Query search error for '{query}': {e}")

    log(f"Couldn't find rating on goodreads for {title}")
    return None, None


def rateBooks(books: List, update_rating_callback: Callable):
    """Orchestrates multi-threaded rating updates for a list of books."""
    similarity_engine = SimilarityEngine()
    max_workers = 2 # Keep it low to avoid aggressive blocks

    def _thread_worker(book):
        try:
            rating, gr_url = getRating(book, similarity_engine)
            # Update the source database via callback
            update_rating_callback(rowid=book.rowid, rating=rating, goodreads_url=gr_url)
        except Exception as e:
            log(f"❌ Critical Error on row {getattr(book, 'rowid', 'unknown')}: {e}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_thread_worker, books)
