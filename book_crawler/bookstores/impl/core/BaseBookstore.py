from abc import ABC, abstractmethod

class BaseBookstore(ABC):
    def __init__(self, url, name, page_query, add_book_callback):
        """
        Initialize common attributes for all Bookstores.
        """
        self.url = url
        self.name = name
        self.page_query = page_query # used to traverse the webpage
        self.add_book_callback = add_book_callback

    @abstractmethod
    def get_books(self):
        """
        Abstract method to fetch books.
        Subclasses must implement this method.
        """
        pass
