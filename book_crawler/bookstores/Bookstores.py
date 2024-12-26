import threading

from book_crawler.bookstores.impl.AnticariatUnuBookstore import AnticariatUnu
from book_crawler.bookstores.impl.TargulCartiiBookstore import TargulCartii
from book_crawler.bookstores.impl.AnticExLibrisBookstore import AnticExLibris

class Bookstores:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _add_book_callback(self, bookstore, book):
        self.db_manager.add_book(bookstore, book)

    def get_books(self):
        bookstores = [
            AnticariatUnu(self._add_book_callback),
            AnticExLibris(self._add_book_callback),
            TargulCartii(self._add_book_callback)
        ]

        # TODO reset db
        for bookstore in bookstores:
            self.db_manager.reset_books_db(bookstore.name)

        threads = []
        for i in range(len(bookstores)):
            threads.append(threading.Thread(target=self._get_books_helper, args=(bookstores[i],)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def _get_books_helper(self, bookstore_obj):
        bookstore_obj.get_books()
