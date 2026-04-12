import re
from dataclasses import asdict, dataclass, field
from enum import Enum


class BookCategory(Enum):
    LITERATURE = "Literature"
    HISTORY = "History"
    SCIENCE = "Science"
    ARTS = "Arts"
    SPIRITUALITY = "Spirituality"
    HOBBIES = "Hobbies"
    PERSONAL_DEVELOPMENT = "Personal Development"
    BUSINESS = "Business"
    KIDS_YA = "Kids & Young Adult"
    OTHER = "Other"
    NONE = "None"


@dataclass
class Offer:
    store: str
    url: str
    price: float

    def __post_init__(self) -> None:
        self.price = float(self.price) if self.price is not None else None
        self.url = self.url.replace(" ", "%20")


@dataclass
class Book:
    title: str
    author: str = None
    isbn: str = None
    category: "BookCategory" = None
    offers: list["Offer"] = field(default_factory=list)
    rating: float | None = None
    goodreads_url: str | None = None

    def __post_init__(self) -> None:
        """Automatically sanitizes strings after initialization."""
        self.title = self._clean(self.title)
        self.author = self._clean(self.author) if self.author is not None else None
        self.isbn = self._clean(self.isbn) if self.isbn is not None else None
        self.rating = float(self.rating) if self.rating is not None else None
        # Default to NONE category if not provided
        if self.category is None:
            self.category = BookCategory.NONE

        if self.goodreads_url:
            self.goodreads_url = (
                self._clean(self.goodreads_url).replace(" ", "%20") if self.goodreads_url is not None else None
            )

    def _clean(self, value: str | None) -> str | None:
        """Replaces all whitespace sequences (\t, \n, multiple spaces) with one space."""
        if not value:
            return None
        # \s+ matches one or more whitespace characters
        return re.sub(r"\s+", " ", value).strip()

    def to_dict(self):
        data = asdict(self)
        data["category"] = self.category.value
        return data
