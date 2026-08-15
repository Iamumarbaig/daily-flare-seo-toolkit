from daily_flare_seo import __version__
from daily_flare_seo.__main__ import suspicious_filename
from daily_flare_seo.content import content_intelligence
from daily_flare_seo import indexing


def test_version():
    assert __version__ == "0.6.1"


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


def test_sitemap_content_type_rejects_binary_only():
    assert indexing._is_xml_response({"content_type": "application/xml; charset=utf-8"})
    assert indexing._is_xml_response({"content_type": "text/plain; charset=utf-8"})
    assert not indexing._is_xml_response({"content_type": "application/octet-stream"})


def test_indexing_checks_both_host_variants_without_writes(monkeypatch):
    def fake_check_url(url):
        if url.endswith("thedailyflare.com/"):
            return {"url": url, "status": 200, "final_url": url, "content_type": "text/html", "x_robots_tag": None}
        return {"url": url, "status": 301, "final_url": "https://thedailyflare.com/", "content_type": "text/html", "x_robots_tag": None}

    monkeypatch.setattr(indexing, "check_url", fake_check_url)
    result = indexing.inspect_indexing_readiness("https://thedailyflare.com")
    urls = {item["url"] for item in result["checks"]["host_variants"]}
    assert urls == {"https://thedailyflare.com/", "https://www.thedailyflare.com/"}
    assert any(item["check"] == "host-variant" for item in result["findings"])
