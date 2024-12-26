import inspect

from rapidfuzz import fuzz

def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))

def _normalize_book_name(book_name):
    book_name = book_name.lower()

    return book_name

def getSimilarity(text1, text2):
    return fuzz.ratio(_normalize_book_name(text1), _normalize_book_name(text2))
