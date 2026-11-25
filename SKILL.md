---
name: traffic-drop-detective
description: Work out why organic traffic fell. Reads a daily Search Console export (API, Looker Studio or BigQuery bulk export, by page or page+query), groups pages by URL folder, and labels each group AI OVERVIEW / SERP CHANGE, RANKING LOSS IN UPDATE WINDOW, SEASONAL, SITE CHANGE or DEMAND DROP with a confidence level and the numbers behind it. Estimates clicks lost per page. Checks drops against confirmed Google core and spam updates from the Search Status Dashboard. Use when the user says "why did my traffic drop", "was it the core update", "is this AI Overviews", "clicks fell but rankings did not", "traffic drop analysis", "diagnose a Search Console drop".
---

# Traffic drop detective

The script labels patterns. A label is a lead to check, not a proven cause.

## Steps

1. Ask for: the daily Search Console file, the rough drop date (optional, the script can find it), and any site changes (migrations, template, robots, redirects, CMS work) with dates and the folder each touched.
2. Check the file has a date column. The Search Console web UI CSVs (Queries.csv, Pages.csv) have no date per page and will be rejected. Accepted: API rows, Looker Studio or Sheets exports, or the BigQuery bulk export (`data_date`, `url`, `query`, `sum_position`, `impressions`, `clicks`). See `references/input-formats.md`.
3. If the user gave site changes, write `changes.csv` with columns `date,note,path_prefix`. Leave `path_prefix` empty for sitewide changes.
4. Run from the skill folder:

```bash
uv run --python 3.12 scripts/detect.py --gsc daily.csv [--drop-date YYYY-MM-DD] \
  [--changes changes.csv] [--window-days 28] [--depth 1] --out report.md --json report.json
```

5. Read the report. For each folder, say the label, the confidence and the numbers. Say plainly when several patterns fit and which one the precedence picked.
6. Suggest the next check per label (below). Do not claim a cause.

## How labels work

Before and after windows are `--window-days` long (default 28) either side of the drop date. A folder needs a clicks per day fall of at least 15% (`--drop-pct`) to be labelled. CTR is clicks divided by impressions. Position is weighted by impressions.

| Label | Rule |
|---|---|
| SEASONAL | The same weeks 364 days earlier fell at least as much. Needs a year of data. |
| SITE CHANGE | A logged change in scope happened 0 to 7 days before the drop date. |
| RANKING LOSS IN UPDATE WINDOW | Position worsened by 1.0 or more and the drop date is inside a confirmed update window (plus 3 days). |
| AI OVERVIEW / SERP CHANGE | Impressions within 10%, CTR down 20% or more, position moved less than 1.0. |
| DEMAND DROP | Impressions down 15% or more, position moved less than 1.0, CTR not down 20%. |

Precedence when several fit: SEASONAL, SITE CHANGE, RANKING LOSS, AI OVERVIEW, DEMAND. Confidence is HIGH with one match, MEDIUM with two or more, LOW (UNEXPLAINED) with none.

Next checks: AI OVERVIEW, search the top queries by hand and look for an AI answer. RANKING LOSS, compare with pages that gained in the same window. SEASONAL, check last year's chart for the same weeks. SITE CHANGE, diff the change (redirects, canonicals, internal links, noindex). DEMAND, check Google Trends for the topic.

## Update list

`references/google-updates.json` holds core and spam updates from the Google Search Status Dashboard, 2024-03 to 2026-11, each with a source URL and `verified: true`. The December 2026 core update is only pre-announced (no end date), so it is never matched. Refresh the file from https://status.search.google.com/products/rGHU1u87FJnkP6W2GwMi/history before important work. If you add an update you cannot confirm there, set `"verified": false`.

## Search Console logging error

When the windows overlap 2025-05-13 to 2026-04-27, the report adds a note quoting Google's data anomalies page: a logging error affected impressions, CTR and position, and clicks were not affected. Source: https://support.google.com/webmasters/answer/6211453. Check that page for newer entries.

## Limits

- Estimates only. Clicks lost is a baseline gap, not a measured loss.
- Windows around Google updates overlap. Rollouts take weeks.
- A folder with under 30 clicks in the before window is skipped.
- This is a helper, not professional advice. Check the figures before you act.
