#!/usr/bin/env python3
"""Build synthetic fixtures. Drop date 2026-06-24, 28-day windows. Hand-derived numbers are in run.sh."""
import csv, datetime as dt, os
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
os.makedirs(F, exist_ok=True)
D0 = dt.date(2026, 6, 24)
one = dt.timedelta(days=1)
# page, (impr, clicks, pos) before, (impr, clicks, pos) after, prior-year rows?
PAGES = [
    ("https://example.com/guides/seo-basics", (1000, 100, 3.0), (1000, 50, 3.0), False),   # AI overview
    ("https://example.com/news/launch", (1000, 100, 3.0), (700, 40, 6.0), False),          # update window
    ("https://example.com/tools/calculator", (1000, 100, 3.0), (500, 50, 3.0), False),     # site change
    ("https://example.com/shop/widgets", (1000, 100, 3.0), (600, 60, 3.0), False),         # demand
    ("https://example.com/summer/sandals", (1000, 100, 3.0), (600, 60, 3.0), True),        # seasonal
    ("https://example.com/about/team", (500, 20, 6.0), (500, 20, 6.0), False),             # stable
]
with open(os.path.join(F, "gsc-daily.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "page", "clicks", "impressions", "ctr", "position"])
    for page, b, a, prior in PAGES:
        for k in range(28):
            for d0, v in ((D0 - 28 * one + k * one, b), (D0 + k * one, a)):
                w.writerow([d0, page, v[1], v[0], "%.4f" % (v[1] / v[0]), v[2]])
                if prior:
                    w.writerow([d0 - 364 * one, page, v[1], v[0], "%.4f" % (v[1] / v[0]), v[2]])
with open(os.path.join(F, "changes.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "note", "path_prefix"])
    w.writerow(["2026-06-20", "Moved tools to new template", "/tools/"])
    w.writerow(["2026-06-21", "Blog redesign", "/blog/"])
    w.writerow(["2026-04-01", "Sitewide footer change", ""])
# BigQuery-shape sample (url table): sum_position is zero-based. position = sum/impr + 1
with open(os.path.join(F, "bq-url.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["data_date", "url", "query", "sum_position", "impressions", "clicks"])
    for k in range(28):
        w.writerow([D0 - 28 * one + k * one, "https://example.com/a/x", "q1", 200, 100, 10])  # pos 3.0
        w.writerow([D0 + k * one, "https://example.com/a/x", "q1", 200, 100, 3])
# windows that overlap the official logging-error window (ends 2026-04-27)
with open(os.path.join(F, "overlap.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Date", "Page", "Clicks", "Impressions", "CTR", "Position"])
    d1 = dt.date(2026, 3, 27)
    for k in range(28):
        w.writerow([(d1 - 28 * one + k * one).strftime("%Y%m%d"), "https://example.com/a/x", 100, 1000, "10%", 3])
        w.writerow([(d1 + k * one).strftime("%Y%m%d"), "https://example.com/a/x", 40, 1000, "4%", 3])
# UI-style file with no date column: must be rejected
with open(os.path.join(F, "ui-pages-no-date.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Top pages", "Clicks", "Impressions", "CTR", "Position"])
    w.writerow(["https://example.com/a", 10, 100, "10%", 3.2])
