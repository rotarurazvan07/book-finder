import pytest
import os
import sqlite3
from book_framework.BooksManager import BooksManager
from book_framework.core.Book import Book, Offer, BookCategory

def test_books_manager_create_and_add(tmp_path):
    db_file = tmp_path / "test.db"
    manager = BooksManager(str(db_file))

    # Setup test book
    book = Book(
        isbn="12345",
        title="Test Book",
        author="Test Author",
        category=BookCategory.LITERATURE,
        offers=[Offer(store="Store1", url="http://s1/1", price=10.5)]
    )

    manager.add_book(book)

    # Check if added
    df = manager.fetch_all_as_dataframe()
    assert len(df) == 1
    assert df.iloc[0]['title'] == "Test Book"
    assert df.iloc[0]['price'] == 10.5

    manager.close()

def test_books_manager_update_rating(tmp_path):
    db_file = tmp_path / "test_rate.db"
    manager = BooksManager(str(db_file))

    book = Book(
        title="To be rated",
        offers=[Offer(store="S1", url="http://s1/2", price=5.0)]
    )
    manager.add_book(book)

    df = manager.fetch_all_as_dataframe()
    rowid = df.iloc[0]['rowid']

    manager.update_rating_callback(rowid, 4.5, "http://gr/rated")

    df_after = manager.fetch_all_as_dataframe()
    assert df_after.iloc[0]['rating'] == 4.5
    assert df_after.iloc[0]['goodreads_url'] == "http://gr/rated"

    manager.close()

def test_merge_databases(tmp_path):
    # Setup two small DBs
    db1_file = tmp_path / "chunk-1.db"
    db2_file = tmp_path / "chunk-2.db"

    m1 = BooksManager(str(db1_file))
    m1.add_book(Book(title="Book 1", offers=[Offer(store="S1", url="http://u1", price=10.0)]))
    m1.close()

    m2 = BooksManager(str(db2_file))
    m2.add_book(Book(title="Book 2", offers=[Offer(store="S2", url="http://u2", price=20.0)]))
    m2.close()

    master_db = tmp_path / "final.db"
    BooksManager.merge_databases(str(tmp_path), str(master_db))

    # Check master
    master_manager = BooksManager(str(master_db))
    df = master_manager.fetch_all_as_dataframe()
    assert len(df) == 2
    titles = set(df['title'].tolist())
    assert "Book 1" in titles
    assert "Book 2" in titles
    master_manager.close()
