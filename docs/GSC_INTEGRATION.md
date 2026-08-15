# Google Search Console integration

The toolkit's `daily_flare_seo.gsc` module is deliberately credential-free. It accepts normalized Search Console/Wizard-style rows and turns them into stable SEO opportunities.

## Why this design

The ChatGPT GSC connection is not a credential that should be copied into GitHub. The toolkit should never contain Google OAuth tokens, cookies, service-account keys, or other secrets.

A future runner can securely fetch GSC data and pass rows to this module through a protected environment or artifact.

## Supported insights

- Low CTR: meaningful impressions + page-one-ish ranking + low CTR.
- Ranking opportunities: positions 4–20 with enough impressions to justify review.
- Aggregate clicks and impressions.

## Safety

The module is analysis-only. It does not submit indexing requests or change Search Console settings.
