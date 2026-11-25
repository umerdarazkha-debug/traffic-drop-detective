#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
PY="uv run --python 3.12 scripts/detect.py"
F=tests/fixtures
fail=0
python3 tests/build_fixtures.py || { echo "fixture build failed"; exit 1; }
has() { if grep -qF -- "$3" <<<"$2"; then echo "ok   $1"; else echo "FAIL $1: missing '$3'"; fail=1; fi; }
not() { if grep -qF -- "$3" <<<"$2"; then echo "FAIL $1: should not contain '$3'"; fail=1; else echo "ok   $1"; fi; }

out=$($PY --gsc $F/gsc-daily.csv --changes $F/changes.csv --drop-date 2026-06-24)
# numbers below are derived by hand from tests/build_fixtures.py
has ai      "$out" "| /guides/ | AI OVERVIEW / SERP CHANGE | HIGH | -50.0% | 1400 |"
has update  "$out" "| /news/ | RANKING LOSS IN UPDATE WINDOW | HIGH | -60.0% | 1680 |"
has change  "$out" "| /tools/ | SITE CHANGE | MEDIUM | -50.0% | 1400 |"
has change2 "$out" "Also consistent with: DEMAND DROP."
has demand  "$out" "| /shop/ | DEMAND DROP | HIGH | -40.0% | 1120 |"
has season  "$out" "| /summer/ | SEASONAL | MEDIUM | -40.0% | 1120 |"
has stable  "$out" "| /about/ | NO MEANINGFUL DROP | n/a | +0.0% | 0 |"
has pagelost "$out" "| https://example.com/guides/seo-basics | 2800 | 1400 | 1400 | 1400 |"
has curveloss "$out" "| https://example.com/news/launch | 2800 | 1120 | 1680 | 0 |"
# the blog-only change and the old sitewide change must not trigger SITE CHANGE elsewhere
not blogchg "$out" "| /guides/ | SITE CHANGE"
not logging-note-absent "$out" "logging error"

out=$($PY --gsc $F/gsc-daily.csv --changes $F/changes.csv)
has autodrop "$out" "Drop date: 2026-06-24 (auto-detected"

# BigQuery shape: sum_position 200 / impressions 100 -> position 3.00 (zero-based sum + 1)
out=$($PY --gsc $F/bq-url.csv --drop-date 2026-06-24)
has bq-pos "$out" "avg position 3.00 -> 3.00"
has bq-ai "$out" "| /a/ | AI OVERVIEW / SERP CHANGE | HIGH | -70.0% | 196 |"

# GSC logging note appears only when windows overlap the official window
out=$($PY --gsc $F/overlap.csv --drop-date 2026-03-27)
has logging-note "$out" "logging error between 2025-05-13 and 2026-04-27"
has logging-src "$out" "https://support.google.com/webmasters/answer/6211453"

# a UI export with no date column must fail
$PY --gsc $F/ui-pages-no-date.csv >/dev/null 2>&1 && { echo "FAIL no-date accepted"; fail=1; } || echo "ok   no-date rejected"

# reference file sanity: every update has a source URL; the pending update is never matched
jq -e '[.updates[] | select(.use_for_matching==true) | .source_url | startswith("https://status.search.google.com/")] | all' references/google-updates.json >/dev/null && echo "ok   updates-sources" || { echo "FAIL updates-sources"; fail=1; }
jq -e '[.updates[] | select(.status=="preannounced") | .use_for_matching] | all(. == false)' references/google-updates.json >/dev/null && echo "ok   pending-unmatched" || { echo "FAIL pending"; fail=1; }

[ $fail -eq 0 ] && echo "ALL PASS" || { echo "FAILED"; exit 1; }
