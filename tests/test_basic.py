from daily_flare_seo import __version__
from daily_flare_seo.__main__ import suspicious_filename, related_pages


def test_version():
    assert __version__ == "0.1.0"


def test_detects_generic_image_filename():
    assert suspicious_filename("https://thedailyflare.com/wp-content/uploads/2026/08/file_000000abc123.png")


def test_allows_descriptive_filename():
    assert suspicious_filename("https://thedailyflare.com/wp-content/uploads/2026/08/iran-us-strait-hormuz.jpg") is None


def test_related_pages_ranks_shared_topic():
    page = {"url": "https://thedailyflare.com/a", "title": "AI infrastructure investment"}
    pages = [
        page,
        {"url": "https://thedailyflare.com/b", "title": "AI infrastructure spending grows"},
        {"url": "https://thedailyflare.com/c", "title": "Hollywood actor wins award"},
    ]
    results = related_pages(page, pages)
    assert results and results[0]["url"] == "https://thedailyflare.com/b"
