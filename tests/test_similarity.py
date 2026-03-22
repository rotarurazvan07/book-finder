import pytest
from book_framework.SimilarityEngine import SimilarityEngine

def test_similarity_engine_singleton():
    cfg1 = {"threshold": 70}
    cfg2 = {"threshold": 80}

    # Initialize first time
    engine1 = SimilarityEngine(cfg1)
    # Subsequent call with different data
    engine2 = SimilarityEngine(cfg2)

    assert engine1 is engine2
    # Ensure it's still 70 (first init won)
    assert engine1.similarity_threshold == 70

def test_similarity_basic():
    engine = SimilarityEngine({"threshold": 70})

    # Matching titles
    match, score = engine.is_similar("The Great Gatsby", "Great Gatsby, The")
    assert match is True

    # Not matching
    match, score = engine.is_similar("The Great Gatsby", "Moby Dick")
    assert match is False

def test_similarity_normalization():
    engine = SimilarityEngine({"threshold": 70})
    # Diacritics and special characters
    match, _ = engine.is_similar("Târgul Cărții", "Targul Cartii")
    assert match is True

    match, _ = engine.is_similar("Ion (Liviu Rebreanu)", "Ion")
    assert match is True

def test_similarity_caching():
    engine = SimilarityEngine({"threshold": 70})

    # First call
    match1, score1 = engine.is_similar("Original Title", "Original Title (Ed. 2)")

    # Second call (should be cached)
    match2, score2 = engine.is_similar("Original Title", "Original Title (Ed. 2)")

    assert match1 == match2
    assert score1 == score2
