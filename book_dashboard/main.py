"""
Book Finder, 2024
"""

from flask import Flask, render_template, request

from book_framework.DatabaseManager import DatabaseManager

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html', buttons=db_manager.fetch_bookstores())


@app.route('/bookstore')
def bookstore():
    bookstore = request.args.get('name')
    books = db_manager.fetch_books_data(bookstore)
    books.sort(key=lambda x:x.rating, reverse=True)
    return render_template('bookstore.html', bookstore=bookstore, books=books)


if __name__ == "__main__":
    db_manager = DatabaseManager()

    app.run(debug=False, port=4999)
