from __future__ import annotations

from urllib.parse import urljoin, urlparse
import requests

UA = "DailyFlareSEOToolkit/0.4 (+https://thedailyflare.com/)"
TIMEOUT = 15


def check_url(url: str) -> dict:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        return {
            "url": url,
            "status": r.status_code,
            "original_status": r.history[0].status_code if r.history else r.status_code,
            "final_url": r.url,
            "redirect_count": len(r.history),
            "redirect_chain": [
                {"status": hop.status_code, "url": hop.url, "location": hop.headers.get("location")}
                for hop in r.history
            ],
            "content_type": r.headers.get("content-type", ""),
            "x_robots_tag": r.headers.get("x-robots-tag"),
        }
    except requests.RequestException as exc:
        return {"url": url, "error": str(exc)}


def _is_xml_response(check: dict) -> bool:
    content_type = (check.get("content_type") or "").lower()
    return "xml" in content_type or "text/plain" in content_type


def inspect_indexing_readiness(base_url: str) -> dict:
    base = base_url.rstrip("/")
    parsed = urlparse(base)
    checks = {}

    robots_url = urljoin(base + "/", "robots.txt")
    checks["robots_txt"] = check_url(robots_url)
    checks["sitemap_xml"] = check_url(urljoin(base + "/", "sitemap.xml"))
    checks["wp_sitemap_xml"] = check_url(urljoin(base + "/", "wp-sitemap.xml"))
    checks["sitemap_index_xml"] = check_url(urljoin(base + "/", "sitemap_index.xml"))

    preferred_host = parsed.netloc
    bare_host = preferred_host[4:] if preferred_host.startswith("www.") else preferred_host
    variant_hosts = [bare_host, f"www.{bare_host}"]
    variants = [f"https://{host}/" for host in dict.fromkeys(variant_hosts)]
    checks["host_variants"] = [check_url(v) for v in variants]

    findings = []
    robots = checks["robots_txt"]
    if robots.get("status") != 200:
        findings.append({"severity": "warning", "check": "robots.txt", "message": "robots.txt was not returned with HTTP 200."})
    elif robots.get("content_type") and "html" in robots["content_type"].lower():
        findings.append({"severity": "warning", "check": "robots.txt", "message": "robots.txt returned HTML instead of a plain-text response; verify the endpoint is not being rewritten."})
    if robots.get("x_robots_tag") and "noindex" in robots["x_robots_tag"].lower():
        findings.append({"severity": "high", "check": "robots.txt", "message": "X-Robots-Tag contains noindex on robots.txt response."})

    sitemap_keys = ("sitemap_xml", "wp_sitemap_xml", "sitemap_index_xml")
    sitemap_ok = any(checks[k].get("status") == 200 and _is_xml_response(checks[k]) for k in sitemap_keys)
    if not sitemap_ok:
        findings.append({"severity": "high", "check": "sitemap", "message": "No checked sitemap endpoint returned a valid HTTP 200 XML/text response."})
    else:
        for key in sitemap_keys:
            check = checks[key]
            if check.get("status") == 200 and not _is_xml_response(check):
                findings.append({"severity": "warning", "check": key, "message": "Sitemap endpoint returned HTTP 200 but its content type does not look like XML/text; verify the response body."})

    preferred_url = f"https://{preferred_host}/"
    for variant in checks["host_variants"]:
        if variant.get("status") not in (200, 301, 302, 307, 308):
            continue
        final = variant.get("final_url", "")
        if not final:
            continue
        final_host = urlparse(final).netloc
        if final_host != preferred_host:
            findings.append({
                "severity": "info",
                "check": "host-variant",
                "message": f"Host variant {variant['url']} resolves to {final}; verify the preferred canonical host is {preferred_url}.",
            })
        elif variant.get("url") != preferred_url and variant.get("redirect_count", 0) == 0 and variant.get("status") == 200:
            findings.append({
                "severity": "warning",
                "check": "host-variant",
                "message": f"Alternate host {variant['url']} returns HTTP 200 without redirecting to the preferred host {preferred_url}.",
            })
        elif variant.get("url") != preferred_url and variant.get("redirect_count", 0) > 1:
            findings.append({
                "severity": "info",
                "check": "host-variant",
                "message": f"Alternate host {variant['url']} reaches the preferred host after {variant['redirect_count']} redirects; consider reducing the redirect chain.",
            })

    return {
        "site": base,
        "read_only": True,
        "checks": checks,
        "findings": findings,
        "note": "Search-engine index status cannot be truthfully inferred from HTTP checks alone. Connect official Google/Bing/Yandex webmaster APIs or inspect their webmaster consoles for definitive index status.",
    }
