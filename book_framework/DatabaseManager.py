from pymongo import MongoClient

from book_crawler.bookstores.impl.core.Book import Book


class DatabaseManager:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['book-finder']

    def fetch_bookstores(self):
        return self.db.list_collection_names()

    def fetch_books_data(self, bookstore):
        books = []
        for book in self.db[bookstore].find():
            # delete _id, not used
            books.append(Book(**({k: v for k, v in book.items() if k != '_id'})))
        return books

    def add_book(self, bookstore, book):
        self.db[bookstore].insert_one(book.__dict__)

    def reset_books_db(self, bookstore):
        self.db[bookstore].delete_many({})