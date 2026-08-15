# Daily Flare SEO Toolkit

A safe, read-only SEO auditing toolkit for The Daily Flare (`thedailyflare.com`).

## v1 goals

- Crawl a site or sitemap without making changes.
- Audit page titles, meta descriptions, headings, canonical URLs, robots directives, links, and images.
- Flag weak or missing image `alt` text and suspicious generated filenames.
- Check `robots.txt` and sitemap availability.
- Produce a machine-readable JSON report and a human-readable summary.
- Run in GitHub Actions so every audit is reproducible.

## Safety

This first version is **read-only**. It does not publish, delete, rename, or modify anything on WordPress, Google Search Console, Bing, or Yandex.

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
2. Add Bing/Yandex indexing diagnostics where APIs permit.
3. Add WordPress Media Library metadata recommendations.
4. Add internal-link recommendations based on existing Daily Flare articles.
5. Add optional, explicitly approved write operations through WordPress.
