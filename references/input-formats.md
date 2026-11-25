# Input formats

Looked up on 2026-11-26.

## BigQuery bulk export (official)
Source: https://support.google.com/webmasters/answer/12917991
- Tables `searchdata_site_impression` and `searchdata_url_impression`; `ExportLog`.
- URL table fields include `data_date`, `url`, `query`, `is_anonymized_query`, `sum_position`, `impressions`, `clicks`, `country`, `device`, `search_type`.
- `sum_position` is zero-based. Average position = SUM(sum_position) / SUM(impressions) + 1. The site table uses `sum_top_position` the same way.
- Rows are not pre-aggregated. This skill aggregates them.
- Export with: `SELECT data_date AS date, url AS page, query, SUM(sum_position) AS sum_position, SUM(impressions) AS impressions, SUM(clicks) AS clicks FROM searchconsole.searchdata_url_impression GROUP BY 1,2,3`

## Search Console web UI export (not usable here)
Source: https://support.google.com/webmasters/answer/12919797
Exports hold the chart and table data, up to 1,000 rows, with `~` and `-` exported as zeros. Exact CSV header spellings are not published in the help pages (UNVERIFIED), so the loader matches common names ("Top pages", "Top queries", "Clicks", "Impressions", "CTR", "Position"). A table export has no date per page, so this skill rejects it.

## API / Looker Studio / Sheets
Rows with dimensions date, page, query and metrics clicks, impressions, ctr, position. Dates as `YYYY-MM-DD` or `YYYYMMDD`. CTR may be a fraction or `12%` (it is recomputed anyway). Lines starting with `#` are skipped.
