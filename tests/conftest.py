"""Shared fixtures for BooksManager tests."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from book_framework.BooksManager import BooksManager
from book_framework.core.Book import Book, BookCategory, Offer


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Create a temporary database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def books_manager(temp_db_path: str) -> BooksManager:
    """Create a BooksManager instance with a temporary database."""
    with patch("book_framework.BooksManager.BufferedStorageManager.__init__") as mock_init:
        mock_init.return_value = None
        manager = BooksManager(temp_db_path)
        manager.db_path = temp_db_path
        manager.table_name = "books"
        manager._buffer = pd.DataFrame()
        manager._dirty = False
        manager._lock = MagicMock()
        manager.db_lock = MagicMock()
        manager.conn = MagicMock()
        manager._last_mtime = None
        return manager


@pytest.fixture
def sample_book_single_offer() -> Book:
    """Create a sample book with a single offer."""
    return Book(
        title="Test Book",
        author="Test Author",
        isbn="1234567890",
        category=BookCategory.LITERATURE,
        rating=4.5,
        goodreads_url="https://goodreads.com/book/show/123",
        offers=[Offer(store="Store1", url="http://store1.com/book1", price=10.0)],
    )


@pytest.fixture
def sample_book_multiple_offers() -> Book:
    """Create a sample book with multiple offers."""
    return Book(
        title="Another Book",
        author="Another Author",
        isbn="0987654321",
        category=BookCategory.SCIENCE,
        rating=4.0,
        goodreads_url="https://goodreads.com/book/show/456",
        offers=[
            Offer(store="StoreA", url="http://storea.com/book2", price=15.0),
            Offer(store="StoreB", url="http://storeb.com/book2", price=18.0),
            Offer(store="StoreC", url="http://storec.com/book2", price=12.0),
        ],
    )


@pytest.fixture
def sample_book_no_category() -> Book:
    """Create a sample book with no explicit category."""
    return Book(
        title="No Category Book",
        author="Some Author",
        isbn="1111111111",
        category=None,
        offers=[Offer(store="StoreX", url="http://storex.com/book3", price=20.0)],
    )


@pytest.fixture
def sample_book_invalid_title() -> Book:
    """Create a sample book with invalid (empty) title."""
    return Book(
        title="   ",
        author="Author",
        isbn="2222222222",
        category=BookCategory.HISTORY,
        offers=[Offer(store="StoreY", url="http://storey.com/book4", price=5.0)],
    )


@pytest.fixture
def mock_buffer(books_manager: BooksManager) -> MagicMock:
    """Mock the buffer with sample data."""
    buffer_data = {
        "isbn": ["1234567890", "0987654321"],
        "title": ["Test Book", "Another Book"],
        "author": ["Test Author", "Another Author"],
        "category": ["Literature", "Science"],
        "rating": [4.5, 4.0],
        "goodreads_url": ["https://goodreads.com/123", "https://goodreads.com/456"],
        "store": ["Store1", "StoreA"],
        "url": ["http://store1.com/book1", "http://storea.com/book2"],
        "price": [10.0, 15.0],
    }
    books_manager._buffer = pd.DataFrame(buffer_data)
    books_manager._dirty = False
    return books_manager._buffer
