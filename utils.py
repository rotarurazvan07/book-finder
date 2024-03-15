import inspect
import time
from datetime import datetime

import requests
from openpyxl import Workbook
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class Book():
    def __init__(self, title, isbn, author, price, url):
        self.title = title
        self.isbn = isbn
        self.author = author
        self.price = price
        self.url = url
        self.rating = 0

    def __eq__(self, other):
        return isinstance(other, Book) and self.title == other.title

    def __hash__(self):
        return hash(self.title)


class Bookstore():
    def __init__(self, base_address, name, page_query):
        self.base_address = base_address
        self.name = name
        self.page_query = page_query
        self.booklist = []
        self.categories = {}
        self.current_page = 0

    def getCategoryNames(self):
        return list(self.categories.keys())

    def getSearchUrl(self, category):
        return self.categories[category] + self.page_query


def exportBooks(booklist, name):
    workbook = Workbook()
    sheet = workbook.active

    sheet.append(["Title", "ISBN", "Author", "Price", "Book Rating", "URL"])

    for book in booklist:
        sheet.append([book.title, book.isbn, book.author, book.price, book.rating, book.url])

    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    workbook.save(f"{name}_{current_datetime}.xlsx")


def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))


def getSimilarity(text1, text2):
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([text1, text2])
    cosine_sim = cosine_similarity(vectors)[0][1]
    log(f"Similarity between {text1} and {text2}: {cosine_sim}")
    return cosine_sim


def makeRequest(url, max_retries=3):
    log(url)
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                return response, response.text
            else:
                log(f"Failed to fetch URL: {url}. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            log(f"An error occurred: {e}")

        retries += 1
        time.sleep(1)

    log(f"Failed to fetch URL: {url} after {max_retries} retries")
    return None
