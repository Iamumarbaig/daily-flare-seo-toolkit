from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse, unquote
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from .indexing import inspect_indexing_readiness

UA = "DailyFlareSEOToolkit/0.3 (+https://thedailyflare.com/)"
TIMEOUT = 15
STOPWORDS = {"the", "and", "for", "with", "from", "that", "this", "will", "has", "have", "are", "was", "were", "into", "your", "their", "about", "after", "before", "over", "under", "what", "when", "where", "how", "why", "its", "daily", "flare", "news", "says", "said"}


def get(url: str):
    return requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)


def clean_url(url: str) -> str:
    p = urlparse(url)
    return p._replace(fragment="").geturl().rstrip("/") or p.scheme + "://" + p.netloc


def sitemap_urls(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [loc.text.strip() for loc in root.iter() if loc.tag.lower().endswith("loc") and loc.text]


def discover_urls(base: str, limit: int) -> tuple[list[str], dict]:
    diagnostics = {}
    candidates = [urljoin(base, "/sitemap_index.xml"), urljoin(base, "/sitemap.xml"), urljoin(base, "/wp-sitemap.xml")]
    urls: list[str] = []
    seen_sitemaps: set[str] = set()
    for candidate in candidates:
        try:
            r = get(candidate)
            diagnostics[candidate] = {"status": r.status_code, "final_url": r.url}
            if not r.ok or "xml" not in r.headers.get("content-type", ""):
                continue
            found = sitemap_urls(r.text)
            expanded: list[str] = []
            for item in found:
                if item.endswith(".xml") and item not in seen_sitemaps:
                    seen_sitemaps.add(item)
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
    normalized = [clean_url(u) for u in urls if urlparse(u).scheme in {"http", "https"}]
    return list(dict.fromkeys(normalized))[:limit], diagnostics


def suspicious_filename(src: str) -> str | None:
    if not src:
        return "missing-src"
    stem = PurePosixPath(unquote(urlparse(src).path)).stem.lower()
    if not stem:
        return "missing-filename"
    patterns = [r"^file[_-]?[a-z0-9]{6,}$", r"^(image|img|photo|picture)[_-]?[0-9a-z]{5,}$", r"^wp[_-]?[0-9]{5,}$", r"^dsc[_-]?[0-9]{4,}$", r"^pxl[_-]?[0-9]{4,}$", r"^[0-9]{5,}$", r"^[a-f0-9]{16,}$"]
    return "generated-or-generic-filename" if any(re.match(p, stem) for p in patterns) else None


def audit_page(url: str, host: str) -> dict:
    result = {"url": url, "issues": [], "status": None, "internal_links": []}
    try:
        r = get(url)
        result["status"] = r.status_code
        result["final_url"] = clean_url(r.url)
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
    result.update({"title": title, "title_length": len(title), "meta_description": description, "meta_description_length": len(description), "canonical": clean_url(urljoin(r.url, canonical)) if canonical else None, "robots": robots or None, "h1_count": len(h1s), "h1s": h1s[:5]})

    if not title: result["issues"].append("missing-title")
    elif len(title) < 30 or len(title) > 65: result["issues"].append("title-length")
    if not description: result["issues"].append("missing-meta-description")
    elif len(description) < 70 or len(description) > 165: result["issues"].append("meta-description-length")
    if not canonical: result["issues"].append("missing-canonical")
    if len(h1s) == 0: result["issues"].append("missing-h1")
    elif len(h1s) > 1: result["issues"].append("multiple-h1")
    if "noindex" in robots.lower(): result["issues"].append("noindex")

    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        full_src = urljoin(r.url, src) if src else None
        alt = img.get("alt")
        item = {"src": full_src, "alt": alt}
        if alt is None: item["issue"] = "missing-alt"
        elif not alt.strip(): item["issue"] = "empty-alt"
        elif re.search(r"^(file|image|img|wp)[_-]?[0-9a-f]{6,}|^\d{5,}", alt.strip(), re.I): item["issue"] = "generated-looking-alt"
        filename_issue = suspicious_filename(full_src or "")
        if filename_issue: item["filename_issue"] = filename_issue
        images.append(item)
    result["images"] = images
    result["image_issues"] = sum(1 for i in images if i.get("issue") or i.get("filename_issue"))

    for a in soup.find_all("a", href=True):
        target = clean_url(urljoin(r.url, a["href"]))
        if urlparse(target).netloc == host: result["internal_links"].append(target)
    result["internal_links"] = list(dict.fromkeys(result["internal_links"]))
    result["internal_link_count"] = len(result["internal_links"])
    if not result["internal_links"]: result["issues"].append("no-internal-links")
    return result


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in STOPWORDS}


def related_pages(page: dict, pages: list[dict], limit: int = 3) -> list[dict]:
    base_tokens = tokens(page.get("title", ""))
    if not base_tokens: return []
    candidates = []
    for other in pages:
        if other["url"] == page["url"] or not other.get("title"): continue
        other_tokens = tokens(other["title"])
        overlap = base_tokens & other_tokens
        if not overlap: continue
        score = len(overlap) / max(1, len(base_tokens | other_tokens))
        candidates.append({"url": other["url"], "title": other["title"], "score": round(score, 3)})
    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:limit]


def site_intelligence(pages: list[dict]) -> dict:
    title_groups = defaultdict(list)
    desc_groups = defaultdict(list)
    incoming = Counter()
    audited = {p["url"] for p in pages}
    for page in pages:
        if page.get("title"): title_groups[page["title"].strip().lower()].append(page["url"])
        if page.get("meta_description"): desc_groups[page["meta_description"].strip().lower()].append(page["url"])
        for target in page.get("internal_links", []):
            if target in audited and target != page["url"]: incoming[target] += 1
    duplicate_titles = [{"title": key, "urls": urls} for key, urls in title_groups.items() if len(urls) > 1]
    duplicate_descriptions = [{"description": key, "urls": urls} for key, urls in desc_groups.items() if len(urls) > 1]
    orphan_candidates = [{"url": p["url"], "title": p.get("title", ""), "reason": "no incoming internal links within audited pages"} for p in pages if p.get("status") == 200 and incoming[p["url"]] == 0 and p is not pages[0]]
    filename_issues = [{"page": p["url"], "image": i["src"], "issue": i["filename_issue"]} for p in pages for i in p.get("images", []) if i.get("filename_issue")]
    recommendations = [{"source": p["url"], "suggested_targets": related_pages(p, pages), "reason": "page has no internal links; targets are ranked by title-token overlap"} for p in pages if p.get("status") == 200 and p.get("internal_link_count", 0) == 0]
    return {"duplicate_titles": duplicate_titles, "duplicate_meta_descriptions": duplicate_descriptions, "orphan_candidates": orphan_candidates, "suspicious_image_filenames": filename_issues, "internal_link_recommendations": recommendations}


def main():
    parser = argparse.ArgumentParser(description="Read-only SEO audit for Daily Flare")
    parser.add_argument("--url", default="https://thedailyflare.com")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--output", default="report.json")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    host = urlparse(base).netloc
    urls, sitemap = discover_urls(base, args.max_pages)
    if not urls: urls = [base]
    pages = [audit_page(u, host) for u in urls]
    issue_counts = Counter(issue for p in pages for issue in p.get("issues", []))
    intelligence = site_intelligence(pages)
    indexing = inspect_indexing_readiness(base)
    issue_counts.update({"duplicate-titles": len(intelligence["duplicate_titles"]), "duplicate-meta-descriptions": len(intelligence["duplicate_meta_descriptions"]), "orphan-candidates": len(intelligence["orphan_candidates"]), "suspicious-image-filenames": len(intelligence["suspicious_image_filenames"]), "indexing-readiness-findings": len(indexing["findings"])})
    report = {"tool_version": "0.3.0", "site": base, "read_only": True, "sitemap_diagnostics": sitemap, "indexing_readiness": indexing, "pages_audited": len(pages), "issue_counts": dict(issue_counts), "intelligence": intelligence, "pages": pages}
    with open(args.output, "w", encoding="utf-8") as f: json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({"pages_audited": len(pages), "issue_counts": dict(issue_counts), "indexing_findings": len(indexing["findings"]), "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
