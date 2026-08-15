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


def normalize_rows(rows: list[dict]) -> list[dict]:
    """Normalize GSC API/Wizard-style rows into a stable internal shape."""
    normalized = []
    for row in rows:
        keys = row.get("keys", [])
        normalized.append({
            "query": row.get("query") or (keys[0] if len(keys) == 1 else None),
            "page": row.get("page") or (keys[1] if len(keys) > 1 else None),
            "clicks": float(row.get("clicks", 0)),
            "impressions": float(row.get("impressions", 0)),
            "ctr": float(row.get("ctr", 0)),
            "position": float(row.get("position", 0)),
        })
    return normalized


def find_ctr_opportunities(rows: list[dict], min_impressions: int = 20) -> list[GSCInsight]:
    """Flag pages/queries with meaningful impressions but low CTR."""
    out = []
    for r in normalize_rows(rows):
        if r["impressions"] < min_impressions or not r["query"]:
            continue
        # Conservative heuristic: ranking on page 1/near page 1 with little traffic.
        if 1 <= r["position"] <= 12 and r["ctr"] < 0.03:
            out.append(GSCInsight(
                kind="low-ctr",
                severity="medium",
                page=r["page"],
                query=r["query"],
                message="Query has meaningful impressions but a low CTR; review title and meta description.",
                metrics={k: r[k] for k in ("clicks", "impressions", "ctr", "position")},
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
                metrics={k: r[k] for k in ("clicks", "impressions", "ctr", "position")},
            ))
    return out


def summarize(rows: list[dict]) -> dict:
    normalized = normalize_rows(rows)
    return {
        "rows": len(normalized),
        "clicks": sum(r["clicks"] for r in normalized),
        "impressions": sum(r["impressions"] for r in normalized),
        "opportunities": [
            i.__dict__ for i in find_ctr_opportunities(rows) + find_ranking_opportunities(rows)
        ],
    }
