# traffic-drop-detective

Traffic fell and you want to know where to look first. This skill splits the drop by URL folder and tests five patterns against your own numbers.

## Inputs

- Daily Search Console data by page (and optionally query). Columns are matched by name, case-insensitive: `date` / `data_date`, `page` / `url` / `landing page`, `query`, `clicks`, `impressions`, `ctr` (ignored, recomputed), `position` / `average position`, or `sum_position` (BigQuery, zero-based).
- Optional `changes.csv`: `date,note,path_prefix`.
- `references/google-updates.json`: confirmed core and spam updates with start, end and source URL.

Search Console web UI CSV downloads have no daily rows per page, so they cannot be used. See `references/input-formats.md`.

## Install

```bash
git clone https://github.com/umerdarazkha-debug/traffic-drop-detective ~/.claude/skills/traffic-drop-detective
```

Needs `uv`. No other dependencies.

## Use

Ask Claude: "Why did my traffic drop? Here is the daily export." Or run `scripts/detect.py` as shown in `SKILL.md`.

## Test

`bash tests/run.sh`. Six synthetic folders, each built for one pattern, plus a stable folder as the negative case. Offline.

## Limits

Thresholds (15% fall, 20% CTR change, 1.0 position) are judgement calls. A label is a lead, not proof.

## License

MIT
