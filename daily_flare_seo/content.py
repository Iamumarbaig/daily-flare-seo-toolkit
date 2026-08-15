from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "will", "has", "have",
    "are", "was", "were", "into", "your", "their", "about", "after", "before", "over",
    "under", "what", "when", "where", "how", "why", "its", "daily", "flare", "news",
    "says", "said", "amid", "new", "more", "than", "also", "just", "here", "they",
}


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", text.lower())
    return [w for w in words if w not in STOPWORDS]


def keyword_counts(text: str, limit: int = 10) -> list[dict]:
    counts = Counter(tokens(text))
    return [{"keyword": word, "count": count} for word, count in counts.most_common(limit)]


def internal_link_opportunities(pages: list[dict], limit: int = 5) -> list[dict]:
    opportunities = []
    for source in pages:
        source_tokens = set(tokens(source.get("title", "")))
        if not source_tokens:
            continue
        existing = set(source.get("internal_links", []))
        ranked = []
        for target in pages:
            if target["url"] == source["url"] or target["url"] in existing or not target.get("title"):
                continue
            target_tokens = set(tokens(target["title"]))
            overlap = source_tokens & target_tokens
            if overlap:
                score = len(overlap) / max(1, len(source_tokens | target_tokens))
                ranked.append({"url": target["url"], "title": target["title"], "score": round(score, 3), "shared_terms": sorted(overlap)})
        if ranked:
            opportunities.append({"source": source["url"], "source_title": source.get("title", ""), "targets": sorted(ranked, key=lambda x: x["score"], reverse=True)[:limit]})
    return opportunities


def content_intelligence(pages: list[dict]) -> dict:
    all_titles = " ".join(p.get("title", "") for p in pages)
    return {
        "top_site_terms": keyword_counts(all_titles),
        "internal_link_opportunities": internal_link_opportunities(pages),
    }
