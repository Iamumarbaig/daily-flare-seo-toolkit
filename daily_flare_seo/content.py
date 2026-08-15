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


def similarity(title_a: str, title_b: str) -> float:
    a, b = set(tokens(title_a)), set(tokens(title_b))
    if not a or not b:
        return 0.0
    return round(len(a & b) / len(a | b), 3)


def duplicate_topic_candidates(pages: list[dict], threshold: float = 0.45) -> list[dict]:
    results = []
    valid = [p for p in pages if p.get("title")]
    for i, page in enumerate(valid):
        for other in valid[i + 1:]:
            score = similarity(page["title"], other["title"])
            if score >= threshold:
                results.append({
                    "url_a": page["url"],
                    "title_a": page["title"],
                    "url_b": other["url"],
                    "title_b": other["title"],
                    "similarity": score,
                    "action": "review for overlapping topic/cannibalization",
                })
    return sorted(results, key=lambda x: x["similarity"], reverse=True)


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
        "duplicate_topic_candidates": duplicate_topic_candidates(pages),
        "internal_link_opportunities": internal_link_opportunities(pages),
    }
