class BookFinderError(Exception):
    """Base exception for book-finder framework."""
    pass

class ScraperError(BookFinderError):
    """Raised when scraping fails persistently or escalation crashes."""
    pass

class DatabaseError(BookFinderError):
    """Raised on SQLite or data integration failures."""
    pass

class ConfigError(BookFinderError):
    """Raised when configuration files are missing or malformed."""
    pass
