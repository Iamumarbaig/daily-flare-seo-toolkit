from daily_flare_seo.indexing import _is_xml_response


def test_accepts_xml_content_type():
    assert _is_xml_response({"content_type": "application/xml; charset=utf-8"})


def test_accepts_plain_text_for_robots_or_text_sitemaps():
    assert _is_xml_response({"content_type": "text/plain; charset=utf-8"})


def test_rejects_html_content_type():
    assert not _is_xml_response({"content_type": "text/html; charset=utf-8"})
