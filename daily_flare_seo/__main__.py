from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

UA = "DailyFlareSEOToolkit/0.1 (+https://thedailyflare.com/)"
TIMEOUT = 15


def get(url: str):
    return requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)


def clean_url(url: str) -> str:
    p = urlparse(url)
    return p._replace(fragment="").geturl()


def sitemap_urls(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [loc.text.strip() for loc in root.iter() if loc.tag.lower().endswith("loc") and loc.text]


def discover_urls(base: str, limit: int) -> tuple[list[str], dict]:
    diagnostics = {}
    candidates = [urljoin(base, "/sitemap_index.xml"), urljoin(base, "/sitemap.xml")]
    urls: list[str] = []
    for candidate in candidates:
        try:
            r = get(candidate)
            diagnostics[candidate] = {"status": r.status_code, "final_url": r.url}
            if r.ok and "xml" in r.headers.get("content-type", ""):
                found = sitemap_urls(r.text)
                # A sitemap index contains other sitemap URLs. Expand one level.
                expanded = []
                for item in found:
                    if item.endswith(".xml"):
                        try:
                            sr = get(item)
                            if sr.ok:
                                expanded.extend(sitemap_urls(sr.text))
                        except requests.RequestException:
                            pass
                urls.extend(expanded or found)
                if urls:
                    break
        except (requests.RequestException, ET.ParseError) as exc:
            diagnostics[candidate] = {"error": str(exc)}
    return list(dict.fromkeys(clean_url(u) for u in urls))[:limit], diagnostics


def audit_page(url: str, host: str) -> dict:
    result = {"url": url, "issues": [], "status": None}
    try:
        r = get(url)
        result["status"] = r.status_code
        result["final_url"] = r.url
        result["content_type"] = r.headers.get("content-type", "")
        if not r.ok or "html" not in result["content_type"]:
            result["issues"].append("page-not-html-or-not-200")
            return result
    except requests.RequestException as exc:
        result["error"] = str(exc)
        result["issues"].append("request-failed")
        return result

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    description = desc_tag.get("content", "").strip() if desc_tag else ""
    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""
    robots_tag = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    robots = robots_tag.get("content", "").strip() if robots_tag else ""
    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]

    result.update({
        "title": title,
        "title_length": len(title),
        "meta_description": description,
        "meta_description_length": len(description),
        "canonical": urljoin(r.url, canonical) if canonical else None,
        "robots": robots or None,
        "h1_count": len(h1s),
        "h1s": h1s[:5],
    })

    if not title:
        result["issues"].append("missing-title")
    elif len(title) < 30 or len(title) > 65:
        result["issues"].append("title-length")
    if not description:
        result["issues"].append("missing-meta-description")
    elif len(description) < 70 or len(description) > 165:
        result["issues"].append("meta-description-length")
    if not canonical:
        result["issues"].append("missing-canonical")
    if len(h1s) == 0:
        result["issues"].append("missing-h1")
    elif len(h1s) > 1:
        result["issues"].append("multiple-h1")
    if "noindex" in robots.lower():
        result["issues"].append("noindex")

    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        alt = img.get("alt")
        item = {"src": urljoin(r.url, src) if src else None, "alt": alt}
        if alt is None:
            item["issue"] = "missing-alt"
        elif not alt.strip():
            item["issue"] = "empty-alt"
        elif re.search(r"^(file|image|img|wp)[_-]?[0-9a-f]{6,}|^\d{5,}", alt.strip(), re.I):
            item["issue"] = "generated-looking-alt"
        images.append(item)
    result["images"] = images
    result["image_issues"] = sum(1 for i in images if i.get("issue"))

    links = []
    for a in soup.find_all("a", href=True):
        target = clean_url(urljoin(r.url, a["href"]))
        if urlparse(target).netloc == host:
            links.append(target)
    result["internal_link_count"] = len(links)
    if len(links) == 0:
        result["issues"].append("no-internal-links")
    return result


def main():
    parser = argparse.ArgumentParser(description="Read-only SEO audit for Daily Flare")
    parser.add_argument("--url", default="https://thedailyflare.com")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--output", default="report.json")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    host = urlparse(base).netloc
    urls, sitemap = discover_urls(base, args.max_pages)
    if not urls:
        urls = [base]

    pages = [audit_page(u, host) for u in urls]
    issue_counts = Counter(issue for p in pages for issue in p.get("issues", []))
    report = {
        "tool_version": "0.1.0",
        "site": base,
        "read_only": True,
        "sitemap_diagnostics": sitemap,
        "pages_audited": len(pages),
        "issue_counts": dict(issue_counts),
        "pages": pages,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({"pages_audited": len(pages), "issue_counts": dict(issue_counts), "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
