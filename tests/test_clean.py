from daily_flare_seo import __version__
from daily_flare_seo.__main__ import suspicious_filename
from daily_flare_seo.content import content_intelligence
from daily_flare_seo import indexing
from daily_flare_seo.gsc import compare_periods, summarize


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


def test_gsc_summary_and_page_aggregation():
    rows = [
        {"keys": ["alpha", "https://thedailyflare.com/a"], "clicks": 10, "impressions": 100, "ctr": 0.10, "position": 5},
        {"keys": ["beta", "https://thedailyflare.com/a"], "clicks": 5, "impressions": 50, "ctr": 0.10, "position": 9},
    ]
    result = summarize(rows)
    assert result["clicks"] == 15
    assert result["impressions"] == 150
    assert result["ctr"] == 0.1
    assert result["pages"][0]["page"] == "https://thedailyflare.com/a"
    assert result["pages"][0]["position"] == 19 / 3


def test_gsc_period_comparison_exposes_deltas():
    current = [{"keys": ["alpha", "https://thedailyflare.com/a"], "clicks": 15, "impressions": 150, "ctr": 0.10, "position": 4}]
    previous = [{"keys": ["alpha", "https://thedailyflare.com/a"], "clicks": 10, "impressions": 100, "ctr": 0.10, "position": 6}]
    result = compare_periods(current, previous, "page")
    assert result[0]["delta"]["clicks"] == 5
    assert result[0]["delta"]["impressions"] == 50
    assert result[0]["delta"]["position"] == -2
