from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, get_logger

from book_crawler.bookstores.BaseBookstore import BaseBookstore
from book_framework.core.Book import Book, BookCategory, Offer

logger = get_logger(__name__)

TARGUL_CARTII_BASE_URL = "https://www.targulcartii.ro/"
TARGUL_CARTII_NAME = "Targul Cartii"
TARGUL_CARTII_PAGE_QUERY = "?limit=40&page=%s"
MAX_CONCURRENCY = 3


class TargulCartii(BaseBookstore):
    def __init__(self, add_book_callback) -> None:
        super().__init__(add_book_callback)
        self.cats = {
            BookCategory.LITERATURE: [
                "https://www.targulcartii.ro/literatura",
                "https://www.targulcartii.ro/carti-in-limba-straina",
            ],
            BookCategory.KIDS_YA: ["https://www.targulcartii.ro/carti-pentru-copii"],
            BookCategory.ARTS: ["https://www.targulcartii.ro/arta-si-arhitectura"],
            BookCategory.SCIENCE: [
                "https://www.targulcartii.ro/dictionare-cultura-educatie",
                "https://www.targulcartii.ro/stiinta-si-tehnica",
            ],
            BookCategory.HISTORY: ["https://www.targulcartii.ro/istorie-si-etnografie"],
            BookCategory.SPIRITUALITY: ["https://www.targulcartii.ro/spiritualitate"],
            BookCategory.HOBBIES: ["https://www.targulcartii.ro/hobby-si-ghiduri"],
        }

    def get_urls(self):
        """Return list of all page URLs to scrape."""
        urls = []
        all_cat_urls = [url for urls in self.cats.values() for url in urls]

        logger.info(
            "Discovering Targul Cartii URLs from %d categories", len(all_cat_urls)
        )
        for base_cat_url in all_cat_urls:
            try:
                first_page_url = base_cat_url + TARGUL_CARTII_PAGE_QUERY % 1
                html = fetch(first_page_url, stealthy_headers=True)
                if not html:
                    logger.warning("No HTML for URL discovery page: %s", first_page_url)
                    continue

                soup = BeautifulSoup(html, "html.parser")
                total_pages_tag = soup.find("span", class_="pagination_total_pages")
                if not total_pages_tag:
                    urls.append(first_page_url)
                    continue

                max_pages = int(total_pages_tag.get_text())
                for i in range(max_pages):
                    urls.append(base_cat_url + TARGUL_CARTII_PAGE_QUERY % (i + 1))
            except Exception as e:
                logger.error("Error getting URLs for %s: %s", base_cat_url, e)

        logger.info("Discovered %d Targul Cartii URLs", len(urls))
        return urls

    def get_books(self, urls=None) -> None:
        """Entry point for scraping books."""
        target_urls = urls if urls is not None else self.get_urls()
        if not target_urls:
            logger.warning("No URLs found for Targul Cartii")
            return

        logger.info("Scraping %d pages from Targul Cartii", len(target_urls))
        self.scrape_urls(
            target_urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        """Parser for a single page of results."""
        if "Pagina cautata nu exista pe acest site!" in html:
            return

        try:
            soup = BeautifulSoup(html, "html.parser")
            product_grid = soup.find(class_="product-grid")
            if not product_grid:
                return

            book_rows = product_grid.find_all(class_="product-list-row")
            for book_row in book_rows:
                try:
                    title_tag = book_row.find(class_="name").find("a")
                    author_tag = book_row.find(class_="name").find(class_="author_name")
                    price_tag = book_row.find(class_="price_value")

                    if not title_tag or not price_tag:
                        continue

                    book_url = title_tag.get("href")
                    if not book_url.startswith("http"):
                        book_url = TARGUL_CARTII_BASE_URL.rstrip("/") + book_url

                    title = title_tag.get("title")
                    author = author_tag.get_text().strip() if author_tag else None
                    price = float(price_tag.get_text().replace("LEI", "").strip())

                    # Determine category based on URL
                    category = BookCategory.NONE
                    for cat, cat_urls in self.cats.items():
                        if any(u in url for u in cat_urls):
                            category = cat
                            break

                    book = Book(
                        title=title,
                        author=author,
                        isbn=None,  # Will be rated later
                        category=category,
                        offers=[Offer(TARGUL_CARTII_NAME, book_url, price)],
                    )
                    self.add_book(book)
                except Exception as e:
                    logger.debug(
                        "Skipping malformed Targul Cartii row on %s: %s", url, e
                    )
        except Exception as e:
            logger.error("Error parsing page %s: %s", url, e)
