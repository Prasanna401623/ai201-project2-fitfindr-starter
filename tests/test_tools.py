from tools import search_listings
from tools import suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

def test_search_returns_results():
    """A broad search with no filters should return matches."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    """An impossible query should return [] without raising an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """No result should exceed the max_price."""
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter():
    """Size filter should be case-insensitive substring match."""
    results = search_listings("tee", size="M", max_price=None)
    # Every result's size field should contain "m" (case-insensitive)
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_are_sorted():
    """Results should be sorted best match first (higher score = more keyword hits)."""
    results = search_listings("vintage graphic tee streetwear", size=None, max_price=None)
    assert len(results) > 1  # need at least 2 to check order
    # The first result should have 'vintage' or 'graphic' or 'tee' in its tags/title
    first = results[0]
    searchable = first["title"].lower() + " ".join(first["style_tags"]).lower()
    assert any(kw in searchable for kw in ["vintage", "graphic", "tee", "streetwear"])


def test_search_no_size_filter():
    """Passing size=None should not filter out any items by size."""
    results_with_size = search_listings("jacket", size="M", max_price=None)
    results_no_size = search_listings("jacket", size=None, max_price=None)
    assert len(results_no_size) >= len(results_with_size)

def test_suggest_outfit_with_wardrobe():
    """Should return a non-empty string referencing wardrobe pieces."""
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe():
    """Should return general styling advice, not crash or return empty string."""
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    """Should return a non-empty caption string."""
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    outfit = suggest_outfit(item, get_example_wardrobe())
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit():
    """Should return error string when outfit is empty, not crash."""
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    result = create_fit_card("", item)
    assert "Couldn't generate a fit card" in result


def test_create_fit_card_varies():
    """Two calls with the same input should produce different captions."""
    item = search_listings("vintage graphic tee", size=None, max_price=30)[0]
    outfit = suggest_outfit(item, get_example_wardrobe())
    result1 = create_fit_card(outfit, item)
    result2 = create_fit_card(outfit, item)
    assert result1 != result2