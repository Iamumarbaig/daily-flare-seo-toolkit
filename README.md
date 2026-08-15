# Daily Flare SEO Toolkit

A safe, read-only SEO auditing toolkit for The Daily Flare (`thedailyflare.com`).

## Current capabilities — v0.3

- Crawl a site or sitemap without making changes.
- Audit page titles, meta descriptions, headings, canonical URLs, robots directives, links, and images.
- Flag weak or missing image `alt` text and suspicious generated filenames.
- Detect duplicate titles and meta descriptions.
- Identify potential orphan pages within the audited URL set.
- Suggest related internal-link targets.
- Check `robots.txt` and common sitemap endpoints.
- Check HTTP behavior of preferred and `www` host variants.
- Produce a machine-readable JSON report.
- Run reproducible audits through GitHub Actions.

## Indexing monitor

The indexing module checks **indexing readiness**, not claimed search-engine index status. HTTP checks alone cannot prove whether Google, Bing, or Yandex has indexed a URL. Definitive index status should come from the respective webmaster tools/APIs.

## Safety

The toolkit is **read-only**. It does not publish, delete, rename, or modify anything on WordPress, Google Search Console, Bing, or Yandex.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m daily_flare_seo --url https://thedailyflare.com --max-pages 50 --output report.json
```

The crawler follows the site's sitemap when available and stays on the same host.

## Planned next stages

1. Connect the report to Google Search Console data.
2. Add official Bing/Yandex webmaster API diagnostics where credentials and API access permit.
3. Add WordPress Media Library metadata recommendations.
4. Add stronger internal-link recommendations using page content, not only titles.
5. Add optional, explicitly approved WordPress write operations.
