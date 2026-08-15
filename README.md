# Daily Flare SEO Toolkit

A read-only SEO auditing toolkit for The Daily Flare (`thedailyflare.com`) with both a Python audit engine and a native WordPress dashboard plugin.

## v1.0 WordPress plugin

The repository root now contains `daily-flare-seo-toolkit.php`, an installable WordPress plugin. The plugin provides:

- Daily Flare SEO dashboard inside WordPress Admin.
- One-click read-only site audits.
- Page title, meta description, canonical, robots and H1 checks.
- Image ALT and generated/generic filename findings.
- Internal-link diagnostics.
- Duplicate title and meta-description detection.
- Potential orphan-page detection within the audited URL set.
- Sitemap and robots.txt diagnostics.
- Preferred vs `www` host-variant checks.
- Persistent JSON report stored in WordPress.
- Page-level and finding-level report views.
- Administrator-only REST endpoints for reports and audits.
- Optional WordPress Abilities API registration for NIBWP-compatible installations.
- A GitHub Actions workflow that validates PHP and builds an installable ZIP artifact.

## Installation

1. Open the GitHub Actions workflow named **WordPress Plugin Package**.
2. Download the artifact **daily-flare-seo-toolkit-wordpress-plugin**.
3. In WordPress go to Plugins → Add New Plugin → Upload Plugin.
4. Upload `daily-flare-seo-toolkit.zip` and activate it.
5. Open **Daily Flare SEO** in WordPress Admin and run an audit.

The plugin is intentionally read-only in v1.0. It does not publish, delete, rename, or modify posts, media, URLs, Google Search Console, Bing, or Yandex.

## Python engine

The original Python engine remains available for reproducible audits and CI:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m daily_flare_seo --url https://thedailyflare.com --max-pages 50 --output report.json
```

The crawler audits titles, meta descriptions, headings, canonicals, robots directives, links, images, indexing readiness, media recommendations and content/internal-link intelligence.

## Indexing monitor

Indexing readiness is not the same thing as confirmed search-engine index status. HTTP checks cannot prove whether Google, Bing or Yandex has indexed a URL. Definitive index status must come from the relevant webmaster tools/APIs.

## Safety

Credentials are not stored in GitHub. The toolkit remains analysis-first and read-only. Any future WordPress write capability should be added as a separate, explicitly approved feature rather than silently modifying the site.
