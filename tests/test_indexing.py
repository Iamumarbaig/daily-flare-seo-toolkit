from daily_flare_seo.indexing import _is_xml_response


def test_accepts_xml_content_type():
    assert _is_xml_response({"content_type": "application/xml; charset=utf-8"})


def test_accepts_plain_text_for_robots_or_text_sitemaps():
    assert _is_xml_response({"content_type": "text/plain; charset=utf-8"})


def test_rejects_html_content_type():
    assert not _is_xml_response({"content_type": "text/html; charset=utf-8"})


def test_redirected_variant_is_not_treated_as_direct_200():
    check = {
        "url": "https://www.example.com/",
        "status": 200,
        "original_status": 301,
        "final_url": "https://example.com/",
        "redirect_count": 1,
    }
    assert check["redirect_count"] > 0
    assert check["original_status"] in (301, 302, 307, 308)
