from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class GSCInsight:
    kind: str
    severity: str
    page: str | None
    query: str | None
    message: str
    metrics: dict[str, Any]


METRIC_KEYS = ("clicks", "impressions", "ctr", "position")


def normalize_rows(rows: list[dict]) -> list[dict]:
    """Normalize GSC API/Wizard-style rows into a stable internal shape."""
    normalized = []
    for row in rows:
        keys = row.get("keys", []) or []
        normalized.append({
            "query": row.get("query") or (keys[0] if len(keys) >= 1 else None),
            "page": row.get("page") or (keys[1] if len(keys) >= 2 else None),
            "clicks": float(row.get("clicks", 0) or 0),
            "impressions": float(row.get("impressions", 0) or 0),
            "ctr": float(row.get("ctr", 0) or 0),
            "position": float(row.get("position", 0) or 0),
        })
    return normalized


def _aggregate(rows: list[dict], key: str) -> list[dict]:
    """Aggregate rows by page or query while preserving meaningful weighted metrics."""
    buckets: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "weighted_position": 0.0})
    for row in normalize_rows(rows):
        value = row.get(key)
        if not value:
            continue
        bucket = buckets[value]
        bucket["clicks"] += row["clicks"]
        bucket["impressions"] += row["impressions"]
        bucket["weighted_position"] += row["position"] * max(row["impressions"], 0)
    result = []
    for value, bucket in buckets.items():
        impressions = bucket["impressions"]
        clicks = bucket["clicks"]
        result.append({
            key: value,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": clicks / impressions if impressions else 0.0,
            "position": bucket["weighted_position"] / impressions if impressions else 0.0,
        })
    return sorted(result, key=lambda x: x["clicks"], reverse=True)


def summarize_pages(rows: list[dict]) -> list[dict]:
    """Return page-level performance suitable for dashboards and opportunity ranking."""
    return _aggregate(rows, "page")


def summarize_queries(rows: list[dict]) -> list[dict]:
    """Return query-level performance suitable for dashboards and opportunity ranking."""
    return _aggregate(rows, "query")


def compare_periods(current_rows: list[dict], previous_rows: list[dict], dimension: str = "page") -> list[dict]:
    """Compare two GSC periods by page or query without inventing missing data."""
    if dimension not in {"page", "query"}:
        raise ValueError("dimension must be 'page' or 'query'")
    current = {r[dimension]: r for r in _aggregate(current_rows, dimension)}
    previous = {r[dimension]: r for r in _aggregate(previous_rows, dimension)}
    result = []
    for value in sorted(set(current) | set(previous)):
        cur = current.get(value, {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0})
        prev = previous.get(value, {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0})
        result.append({
            dimension: value,
            "current": {k: cur[k] for k in METRIC_KEYS},
            "previous": {k: prev[k] for k in METRIC_KEYS},
            "delta": {k: cur[k] - prev[k] for k in METRIC_KEYS},
        })
    return sorted(result, key=lambda x: abs(x["delta"]["clicks"]) + abs(x["delta"]["impressions"]) / 100, reverse=True)


def classify_movers(current_rows: list[dict], previous_rows: list[dict], dimension: str = "page", limit: int = 10) -> list[dict]:
    """Rank observed winners and losers using GSC period deltas only."""
    comparisons = compare_periods(current_rows, previous_rows, dimension)
    movers = []
    for item in comparisons:
        delta = item["delta"]
        if delta["clicks"] == 0 and delta["impressions"] == 0 and delta["position"] == 0:
            continue
        direction = "up" if delta["clicks"] > 0 or delta["impressions"] > 0 or delta["position"] < 0 else "down"
        impact = abs(delta["clicks"]) + abs(delta["impressions"]) / 100 + abs(delta["position"]) * 2
        movers.append({**item, "direction": direction, "impact_score": round(impact, 3)})
    return sorted(movers, key=lambda x: x["impact_score"], reverse=True)[:limit]


def find_ctr_opportunities(rows: list[dict], min_impressions: int = 20) -> list[GSCInsight]:
    """Flag pages/queries with meaningful impressions but low CTR."""
    out = []
    for r in normalize_rows(rows):
        if r["impressions"] < min_impressions or not r["query"]:
            continue
        if 1 <= r["position"] <= 12 and r["ctr"] < 0.03:
            out.append(GSCInsight(
                kind="low-ctr",
                severity="medium",
                page=r["page"],
                query=r["query"],
                message="Query has meaningful impressions but a low CTR; review title and meta description.",
                metrics={k: r[k] for k in METRIC_KEYS},
            ))
    return out


def find_ranking_opportunities(rows: list[dict], min_impressions: int = 10) -> list[GSCInsight]:
    """Find queries ranking roughly positions 4-20 where optimization may have upside."""
    out = []
    for r in normalize_rows(rows):
        if r["impressions"] < min_impressions or not r["query"]:
            continue
        if 4 <= r["position"] <= 20:
            out.append(GSCInsight(
                kind="ranking-opportunity",
                severity="medium",
                page=r["page"],
                query=r["query"],
                message="Query ranks outside the strongest top positions; consider improving relevance, internal links and on-page coverage.",
                metrics={k: r[k] for k in METRIC_KEYS},
            ))
    return out


def summarize(rows: list[dict]) -> dict:
    normalized = normalize_rows(rows)
    clicks = sum(r["clicks"] for r in normalized)
    impressions = sum(r["impressions"] for r in normalized)
    return {
        "rows": len(normalized),
        "clicks": clicks,
        "impressions": impressions,
        "ctr": clicks / impressions if impressions else 0.0,
        "opportunities": [i.__dict__ for i in find_ctr_opportunities(rows) + find_ranking_opportunities(rows)],
        "pages": summarize_pages(rows),
        "queries": summarize_queries(rows),
    }
