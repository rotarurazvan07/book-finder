from bs4 import BeautifulSoup
from book_crawler.bookstores.BaseBookstore import BaseBookstore
from book_framework.core.Book import Book, Offer, BookCategory
from scrape_kit import ScrapeMode, fetch, get_logger

logger = get_logger(__name__)

ANTICARIAT_UNU_BASE_URL = "https://www.anticariat-unu.ro/"
ANTICARIAT_UNU_NAME = "Anticariat Unu"
ANTICARIAT_UNU_PAGE_QUERY = "/%s" # %s start from 0 and increments 30 by 30
MAX_CONCURRENCY = 3

class AnticariatUnu(BaseBookstore):
    def __init__(self, add_book_callback):
        super().__init__(add_book_callback)
        self.cats = {
            BookCategory.LITERATURE: ["https://www.anticariat-unu.ro/autori-romani-c21",
                                      "https://www.anticariat-unu.ro/literatura-universala-autori-straini-c14",
                                      ],
            BookCategory.HISTORY: ["https://www.anticariat-unu.ro/istorie-c3",
                                   "https://www.anticariat-unu.ro/manuscrise-scrisori-documente-c58",
                                   "https://www.anticariat-unu.ro/ziare-reviste-publicatii-vechi-c52",
                                   "https://www.anticariat-unu.ro/manuale-vechi-c51",
                                   "https://www.anticariat-unu.ro/etnografie-folclor-c22",
                                   "https://www.anticariat-unu.ro/geografie-turism-geologie-astronomie-c19",
                                   ],
            BookCategory.ARTS: ["https://www.anticariat-unu.ro/arta-c4",
                                "https://www.anticariat-unu.ro/arhitectura-c13",
                                "https://www.anticariat-unu.ro/teatru-film-c16",
                                "https://www.anticariat-unu.ro/carti-muzica-c15",
                                ],
            BookCategory.SPIRITUALITY: ["https://www.anticariat-unu.ro/religie-c34",
                                        "https://www.anticariat-unu.ro/filosofie-logica-c17",
                                        "https://www.anticariat-unu.ro/pseudostiinte-ocultism-ezoterism-etc-c41",
                                        ],
            BookCategory.SCIENCE: ["https://www.anticariat-unu.ro/medicina-alopata-si-alternativa-c24",
                                   "https://www.anticariat-unu.ro/stiinte-juridice-c30",
                                   "https://www.anticariat-unu.ro/enciclopedii-carti-de-stiinta-c6",
                                   "https://www.anticariat-unu.ro/biologie-botanica-zoologie-c36",
                                   "https://www.anticariat-unu.ro/chimie-c39",
                                   "https://www.anticariat-unu.ro/matematica-fizica-c40",
                                   "https://www.anticariat-unu.ro/carti-tehnice-c29",
                                   ],
            BookCategory.BUSINESS: ["https://www.anticariat-unu.ro/stiinte-economice-management-si-marketing-c28"],
            BookCategory.PERSONAL_DEVELOPMENT: ["https://www.anticariat-unu.ro/psihologie-c18",
                                                "https://www.anticariat-unu.ro/sociologie-media-jurnalism-advertising-c31",
                                                "https://www.anticariat-unu.ro/pedagogie-c32"],
            BookCategory.KIDS_YA: ["https://www.anticariat-unu.ro/carti-pentru-copii-literatura-populara-benzi-desenate-c45"],
            BookCategory.HOBBIES: ["https://www.anticariat-unu.ro/gastronomie-c25",
                                   "https://www.anticariat-unu.ro/diverse-broderie-tricotaj-fotografie-etc-c37",
                                   "https://www.anticariat-unu.ro/educatie-fizica-sport-c44",
                                   "https://www.anticariat-unu.ro/pescuit-vanatoare-c42"],
        }

    def get_urls(self):
        """Discover available page URLs using binary search on each category."""
        urls = []
        all_cat_urls = [url for urls in self.cats.values() for url in urls]

        logger.info("Discovering Anticariat Unu URLs from %d categories", len(all_cat_urls))
        for base_cat_url in all_cat_urls:
            try:
                resp = fetch(
                    base_cat_url + ANTICARIAT_UNU_PAGE_QUERY % 0,
                    stealthy_headers=True,
                )
                if not resp:
                    logger.warning("No HTML for URL discovery page: %s", base_cat_url)
                    continue

                soup = BeautifulSoup(resp, 'html.parser')
                last_page_tag = soup.find("li", class_="last")
                if not last_page_tag:
                    urls.append(base_cat_url + ANTICARIAT_UNU_PAGE_QUERY % 0)
                    continue

                # Binary search to find the last page with unsold books
                max_pages = int(last_page_tag.find('a')["data-ci-pagination-page"]) - 2
                low, high = 0, max_pages
                last_valid_page = 0

                while low <= high:
                    mid = (low + high) // 2
                    resp_mid = fetch(
                        base_cat_url + (ANTICARIAT_UNU_PAGE_QUERY % (mid * 30)),
                        stealthy_headers=True,
                    )
                    if not resp_mid:
                        high = mid - 1
                        continue

                    soup_mid = BeautifulSoup(resp_mid, 'html.parser')
                    # Count "VANDUT" (Sold) items
                    sold_count = len([s for s in soup_mid.select('span.text-danger')
                                        if s.get_text(strip=True) == "VANDUT"])

                    if sold_count < 30: # If at least one book is available
                        last_valid_page = mid
                        low = mid + 1
                    else:
                        high = mid - 1

                for i in range(last_valid_page + 1):
                    urls.append(base_cat_url + (ANTICARIAT_UNU_PAGE_QUERY % (i * 30)))

            except Exception as e:
                logger.error("Error getting URLs for %s: %s", base_cat_url, e)

        logger.info("Discovered %d Anticariat Unu URLs", len(urls))
        return urls

    def get_books(self, urls=None):
        """Entry point for scraping books."""
        target_urls = urls if urls is not None else self.get_urls()
        if not target_urls:
            logger.warning("No URLs found for Anticariat Unu")
            return

        logger.info("Scraping %d pages from Anticariat Unu", len(target_urls))
        # Concurrency 10-20
        self.scrape_urls(target_urls, self._parse_page, mode=ScrapeMode.FAST, max_concurrency=MAX_CONCURRENCY)

    def _parse_page(self, url, html):
        """Parser for a single page of results."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Extract bookstore's inner list container
            book_anchors = soup.find_all(class_="book")
            if not book_anchors:
                return

            # Determine category based on URL
            category = BookCategory.NONE
            for cat, cat_urls in self.cats.items():
                if any(u in url for u in cat_urls):
                    category = cat
                    break

            for book_anchor in book_anchors:
                try:
                    title_author_tag = book_anchor.find("h3").find("a")
                    price_tag = book_anchor.find(class_="price")

                    if not title_author_tag or not price_tag:
                        continue

                    # skip if already sold (has span.text-danger with VANDUT)
                    sold_tag = book_anchor.find('span', class_='text-danger')
                    if sold_tag and "VANDUT" in sold_tag.get_text():
                        continue

                    title_author = title_author_tag.get_text().strip()
                    title, author = title_author, None

                    # Split title and author using known separators
                    for separator in [" de ", " by ", " par ", "..."]:
                        if separator in title_author:
                            parts = title_author.rsplit(separator, 1)
                            title = parts[0].strip()
                            author = parts[1].split(",")[0].strip()
                            break

                    book_url = title_author_tag['href']
                    if not book_url.startswith("http"):
                        book_url = ANTICARIAT_UNU_BASE_URL.rstrip('/') + book_url

                    price_text = price_tag.get_text().replace("Lei", "").replace(",", ".").strip()
                    price = float(price_text)

                    book = Book(
                        title=title,
                        author=author,
                        isbn=None,
                        category=category,
                        offers=[Offer(ANTICARIAT_UNU_NAME, book_url, price)]
                    )
                    self.add_book(book)
                except Exception as e:
                    logger.debug("Skipping malformed Anticariat Unu row on %s: %s", url, e)
        except Exception as e:
            logger.error("Error parsing page %s: %s", url, e)
