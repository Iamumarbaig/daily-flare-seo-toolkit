from daily_flare_seo import __version__
from daily_flare_seo.__main__ import suspicious_filename
from daily_flare_seo.content import content_intelligence


def test_version():
    assert __version__ == "0.1.0"


def test_detects_generic_image_filename():
    assert suspicious_filename("https://thedailyflare.com/wp-content/uploads/2026/08/file_000000abc123.png")


def test_allows_descriptive_filename():
    assert suspicious_filename("https://thedailyflare.com/wp-content/uploads/2026/08/iran-us-strait-hormuz.jpg") is None


def test_duplicate_topic_detection_removed():
    pages = [
        {"url": "https://thedailyflare.com/a", "title": "AI infrastructure investment", "internal_links": []},
        {"url": "https://thedailyflare.com/b", "title": "AI infrastructure spending grows", "internal_links": []},
    ]
    result = content_intelligence(pages)
    assert "duplicate_topic_candidates" not in result
    assert result["internal_link_opportunities"]
