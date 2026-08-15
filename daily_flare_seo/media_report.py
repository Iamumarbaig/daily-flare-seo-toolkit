from __future__ import annotations

import argparse
import json

from .media import media_recommendation


def build_media_report(pages: list[dict]) -> dict:
    recommendations = []
    for page in pages:
        title = page.get("title", "")
        for image in page.get("images", []):
            rec = media_recommendation(title, image)
            if rec["needs_alt"] or rec["needs_filename"]:
                recommendations.append({"page": page.get("url"), "image": image.get("src"), **rec})
    return {"read_only": True, "recommendations": recommendations, "count": len(recommendations)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate safe Daily Flare media SEO recommendations")
    parser.add_argument("report", help="Existing SEO JSON report")
    parser.add_argument("--output", default="media-recommendations.json")
    args = parser.parse_args()
    with open(args.report, encoding="utf-8") as f:
        report = json.load(f)
    media = build_media_report(report.get("pages", []))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(media, f, indent=2, ensure_ascii=False)
    print(json.dumps({"recommendations": media["count"], "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
