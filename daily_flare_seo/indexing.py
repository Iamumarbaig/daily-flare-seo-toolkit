from __future__ import annotations

from urllib.parse import urljoin, urlparse
import requests

UA = "DailyFlareSEOToolkit/0.3 (+https://thedailyflare.com/)"
TIMEOUT = 15


def check_url(url: str) -> dict:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        return {
            "url": url,
            "status": r.status_code,
            "final_url": r.url,
            "content_type": r.headers.get("content-type", ""),
            "x_robots_tag": r.headers.get("x-robots-tag"),
        }
    except requests.RequestException as exc:
        return {"url": url, "error": str(exc)}


def inspect_indexing_readiness(base_url: str) -> dict:
    base = base_url.rstrip("/")
    parsed = urlparse(base)
    checks = {}

    robots_url = urljoin(base + "/", "robots.txt")
    checks["robots_txt"] = check_url(robots_url)
    checks["sitemap_xml"] = check_url(urljoin(base + "/", "sitemap.xml"))
    checks["wp_sitemap_xml"] = check_url(urljoin(base + "/", "wp-sitemap.xml"))
    checks["sitemap_index_xml"] = check_url(urljoin(base + "/", "sitemap_index.xml"))

    variants = [
        f"https://{parsed.netloc}/",
        f"https://www.{parsed.netloc}/" if not parsed.netloc.startswith("www.") else None,
    ]
    variants = [v for v in variants if v]
    checks["host_variants"] = [check_url(v) for v in dict.fromkeys(variants)]

    findings = []
    robots = checks["robots_txt"]
    if robots.get("status") != 200:
        findings.append({"severity": "warning", "check": "robots.txt", "message": "robots.txt was not returned with HTTP 200."})
    if robots.get("x_robots_tag") and "noindex" in robots["x_robots_tag"].lower():
        findings.append({"severity": "high", "check": "robots.txt", "message": "X-Robots-Tag contains noindex on robots.txt response."})

    sitemap_ok = any(checks[k].get("status") == 200 for k in ("sitemap_xml", "wp_sitemap_xml", "sitemap_index_xml"))
    if not sitemap_ok:
        findings.append({"severity": "high", "check": "sitemap", "message": "No checked sitemap endpoint returned HTTP 200."})

    for variant in checks["host_variants"]:
        if variant.get("status") in (200, 301, 302, 307, 308):
            final = variant.get("final_url", "")
            if final and urlparse(final).netloc != parsed.netloc:
                findings.append({
                    "severity": "info",
                    "check": "host-variant",
                    "message": f"Host variant redirects to {final}; verify this matches the preferred canonical host.",
                })

    return {
        "site": base,
        "read_only": True,
        "checks": checks,
        "findings": findings,
        "note": "Search-engine index status cannot be truthfully inferred from HTTP checks alone. Connect official Google/Bing/Yandex webmaster APIs or inspect their webmaster consoles for definitive index status.",
    }
