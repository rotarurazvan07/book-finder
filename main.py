from book_framework.DatabaseManager import DatabaseManager
from book_framework.SettingsManager import settings_manager
from book_crawler.TargulCartiiBookstore import TargulCartii
from book_crawler.AnticariatUnuBookstore import AnticariatUnu
from book_crawler.PrintreCartiBookstore import PrintreCarti

from book_framework.core.Goodreads import rateBooks
from book_framework.utils import log

class BookFinder:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _add_book_callback(self, book):
        self.db_manager.add_book(book)

    def get_books(self):
        book_finders = [
            TargulCartii(self._add_book_callback),
            PrintreCarti(self._add_book_callback),
            AnticariatUnu(self._add_book_callback)
        ]

        for book_finder in book_finders:
            book_finder.get_books()

def addRating(rowid, rating, goodreads_url):
    if rating is not None and goodreads_url is not None:
        db_manager.update_rating_callback(rowid, rating, goodreads_url)

if __name__ == "__main__":
    settings_manager.load_settings("config")
    db_manager = DatabaseManager(settings_manager.get_config('database_config')["work-db-path"])

    db_manager.reset_db()

    book_finder = BookFinder(db_manager)
    book_finder.get_books()
    rateBooks(db_manager.fetch_all_as_dataframe(), addRating, 12)