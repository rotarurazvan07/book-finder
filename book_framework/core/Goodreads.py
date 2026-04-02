import re
import math
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple, Callable

from scrape_kit import ScrapeMode, SimilarityEngine, get_logger, scrape

logger = get_logger(__name__)

# Constants for Goodreads integration
GOODREADS_URL = "https://www.goodreads.com/"
GOODREADS_SEARCH = GOODREADS_URL + "search?q=%s"
NOT_FOUND_INDICATOR = "looking for a book?"
REJECTED_GOODREADS_TITLES = ["summary", "review", "preview"]


def _clean_text(value) -> Optional[str]:
    """Normalize optional text fields coming from dataframe/json payloads."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if not isinstance(value, str):
        return str(value)
    cleaned = value.strip()
    return cleaned or None


def _parse_isbn_page(html_text: str, search_url: str) -> Tuple[Optional[float], Optional[str]]:
    try:
        if not html_text or NOT_FOUND_INDICATOR in html_text.lower():
            return None, None
        html = BeautifulSoup(html_text, "html.parser")
        rating_val = html.find("div", class_="RatingStatistics__rating").text.strip()
        ratings_count_text = html.find("span", {"data-testid": "ratingsCount"}).text.strip()
        match = re.search(r"\d{1,3}(?:,\d{3})*", ratings_count_text)
        if not match:
            return None, None
        ratings_count = match.group().replace(",", "")
        return float(rating_val) * float(ratings_count), search_url
    except (AttributeError, ValueError, TypeError):
        return None, None


def _parse_search_page(
    html_text: str,
    title: str,
    author: Optional[str],
    similarity_engine: SimilarityEngine,
) -> Tuple[Optional[float], Optional[str]]:
    if not html_text or NOT_FOUND_INDICATOR in html_text.lower():
        return None, None

    try:
        html = BeautifulSoup(html_text, "html.parser")
        book_elements = html.find_all("tr", itemtype="http://schema.org/Book")
    except Exception:
        return None, None

    for book_elem in book_elements:
        try:
            gr_title = (
                book_elem.find("a", class_="bookTitle")
                .find("span", itemprop="name")
                .get_text()
            )
            gr_author = (
                book_elem.find("a", class_="authorName")
                .find("span", itemprop="name")
                .get_text()
            )
        except Exception:
            continue

        if gr_title.lower() in REJECTED_GOODREADS_TITLES:
            continue

        matched, _ = similarity_engine.is_similar(title, gr_title)
        if matched and author and gr_author:
            matched, _ = similarity_engine.is_similar(author, gr_author)
        if not matched:
            continue

        try:
            minirating_text = book_elem.find("span", class_="minirating").text.strip()
            rating_match = re.search(r"(\d+\.\d+)", minirating_text)
            count_match = re.search(r"(\d{1,3}(?:,\d{3})*) ratings?$", minirating_text)
            if not (rating_match and count_match):
                continue
            rating_val = rating_match.group(1)
            ratings_count = count_match.group(1).replace(",", "")
            book_path = book_elem.find("a")["href"]
            return float(rating_val) * float(ratings_count), GOODREADS_URL + book_path
        except Exception:
            continue

    return None, None


def _book_queries(book) -> list[tuple[str, str]]:
    title = _clean_text(getattr(book, "title", None))
    author = _clean_text(getattr(book, "author", None))
    isbn = _clean_text(getattr(book, "isbn", None))

    if not title:
        return []

    queries: list[tuple[str, str]] = []
    if isbn:
        queries.append(("isbn", GOODREADS_SEARCH % quote_plus(str(isbn))))
    if author:
        queries.append(("author_title", GOODREADS_SEARCH % quote_plus(f"{author} {title}")))
    queries.append(("title", GOODREADS_SEARCH % quote_plus(title)))
    return queries


def rateBooks(
    books: List,
    update_rating_callback: Callable,
    similarity_config: Optional[dict] = None,
):
    """Rate books by batch-scraping Goodreads search URLs, then parsing results."""
    if not similarity_config:
        raise ValueError("similarity_config is required for rateBooks with scrape_kit SimilarityEngine")

    similarity_engine = SimilarityEngine(similarity_config)

    # Build (rowid, urls) plans in priority order, then scrape unique URLs in batch.
    plans: dict[int, list[tuple[str, str]]] = {}
    all_urls: list[str] = []
    seen_urls: set[str] = set()

    for book in books:
        try:
            rowid = int(getattr(book, "rowid"))
        except Exception:
            logger.warning("Skipping book without valid rowid: %s", getattr(book, "title", "unknown"))
            continue

        plan = _book_queries(book)
        plans[rowid] = plan
        for _, url in plan:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_urls.append(url)

    responses: dict[str, str] = {}

    def _on_html(url: str, html: str) -> None:
        responses[url] = html

    if all_urls:
        try:
            scrape(all_urls, callback=_on_html, mode=ScrapeMode.STEALTH, max_concurrency=8)
        except Exception as e:
            logger.warning("STEALTH scrape had errors: %s", e)

    for book in books:
        try:
            rowid = int(getattr(book, "rowid"))
        except Exception as e:
            logger.error("Invalid rowid on book %s: %s", getattr(book, "title", "unknown"), e)
            continue

        title = _clean_text(getattr(book, "title", None))
        author = _clean_text(getattr(book, "author", None))
        if not title:
            logger.warning("Skipping row %s because title is missing", rowid)
            continue
        logger.info("Evaluating Goodreads rating for %s by %s", title, author)

        rating: Optional[float] = None
        gr_url: Optional[str] = None

        for query_kind, url in plans.get(rowid, []):
            html_text = responses.get(url)
            if not html_text:
                continue

            if query_kind == "isbn":
                rating, gr_url = _parse_isbn_page(html_text, url)
            else:
                rating, gr_url = _parse_search_page(html_text, title, author, similarity_engine)

            if rating is not None and gr_url:
                break

        if rating is not None and gr_url:
            logger.info("Updating rating for %s by %s: %.2f", title, author, rating)
            update_rating_callback(rowid=rowid, rating=rating, goodreads_url=gr_url)
        else:
            logger.info("No rating found for %s by %s", title, author)
