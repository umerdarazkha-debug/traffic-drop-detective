#!/usr/bin/env python3
"""Classify a Search Console traffic drop per URL folder.

Usage:
  uv run --python 3.12 scripts/detect.py --gsc daily.csv [--drop-date 2026-06-24]
      [--changes changes.csv] [--updates references/google-updates.json]
      [--window-days 28] [--drop-pct 15] [--depth 1] [--out report.md] [--json report.json]
"""
import argparse, csv, datetime as dt, json, os, re, sys
from collections import defaultdict
from urllib.parse import urlparse

NOTICE = "This is a helper, not professional advice. Check the figures before you act."
D = dt.date
ALIASES = {
    "date": ["date", "data_date", "day"],
    "page": ["page", "pages", "url", "top pages", "landing page", "page url", "landing_page"],
    "query": ["query", "queries", "top queries", "keyword", "search query"],
    "clicks": ["clicks", "click"],
    "impressions": ["impressions", "impression"],
    "position": ["position", "average position", "avg position", "avg. position"],
    "sum_position": ["sum_position", "sum_top_position"],
}
# Same-weekday shift for "same period last year".
YEAR_SHIFT = 364


def norm(h):
    return re.sub(r"\s+", " ", h.strip().lstrip("﻿").lower())


def map_headers(headers):
    m = {}
    nh = {norm(h): h for h in headers}
    for key, names in ALIASES.items():
        for n in names:
            if n in nh:
                m[key] = nh[n]
                break
    return m


def num(s, default=0.0):
    if s is None:
        return default
    s = str(s).strip().replace(",", "").replace("%", "")
    if s in ("", "-", "~", "null", "None"):
        return default
    return float(s)


def pdate(s):
    s = str(s).strip()
    if re.fullmatch(r"\d{8}", s):
        return D(int(s[:4]), int(s[4:6]), int(s[6:]))
    return D.fromisoformat(s[:10])


def read_gsc(path):
    """Return rows: (date, page, query, clicks, impressions, position_sum)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        text = [ln for ln in f.read().splitlines() if not ln.startswith("#")]
    rd = csv.DictReader(text)
    m = map_headers(rd.fieldnames or [])
    miss = [k for k in ("date", "page", "clicks", "impressions") if k not in m]
    if miss or not ("position" in m or "sum_position" in m):
        sys.exit("ERROR: %s is missing columns %s (need date, page, clicks, impressions and "
                 "position or sum_position). Headers found: %s. A Search Console UI CSV has no date "
                 "column per page; export from the API, Looker Studio or the BigQuery bulk export."
                 % (path, miss or ["position"], rd.fieldnames))
    rows = []
    for r in rd:
        imp = num(r[m["impressions"]])
        clk = num(r[m["clicks"]])
        if "sum_position" in m and r.get(m["sum_position"], "") != "":
            psum = num(r[m["sum_position"]]) + imp  # zero-based sum -> 1-based
        else:
            psum = num(r[m["position"]]) * imp
        rows.append((pdate(r[m["date"]]), r[m["page"]].strip(), r.get(m.get("query", ""), "") or "", clk, imp, psum))
    if not rows:
        sys.exit("ERROR: no rows in %s" % path)
    return rows


def folder(url, depth):
    p = urlparse(url).path or "/"
    segs = [s for s in p.split("/") if s]
    if len(segs) <= depth and not p.endswith("/"):
        return "/(root)"
    return "/" + "/".join(segs[:depth]) + "/"


def window(rows, a, b):
    return [r for r in rows if a <= r[0] <= b]


def agg(rows):
    c = sum(r[3] for r in rows)
    i = sum(r[4] for r in rows)
    ps = sum(r[5] for r in rows)
    days = len({r[0] for r in rows})
    return dict(clicks=c, impressions=i, ctr=(c / i if i else 0.0), position=(ps / i if i else 0.0), days=days)


def rel(a, b):
    return (a - b) / b if b else 0.0


def detect_drop_date(rows):
    day = defaultdict(float)
    for r in rows:
        day[r[0]] += r[3]
    ds = sorted(day)
    block = [ds[-1]]
    for d in reversed(ds[:-1]):
        if (block[-1] - d).days <= 3:
            block.append(d)
        else:
            break
    block.sort()
    best, bestd = 0.0, None
    k = 14
    for d in block:
        b = [day[x] for x in block if d - dt.timedelta(days=k) <= x < d]
        a = [day[x] for x in block if d <= x < d + dt.timedelta(days=k)]
        if len(b) < k // 2 or len(a) < k // 2:
            continue
        mb, ma = sum(b) / len(b), sum(a) / len(a)
        if mb > 0 and (mb - ma) / mb > best:
            best, bestd = (mb - ma) / mb, d
    return bestd


def load_changes(path):
    out = []
    if not path:
        return out
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r = {norm(k): v for k, v in r.items()}
            out.append(dict(date=pdate(r["date"]), note=r.get("note", ""), prefix=(r.get("path_prefix") or "").strip()))
    return out


def curve(before_rows):
    """Site's own expected CTR by rounded position, from the before window."""
    b = defaultdict(lambda: [0.0, 0.0])
    # aggregate per page first (a page's daily rows share one average position)
    per = defaultdict(lambda: [0.0, 0.0, 0.0])
    for r in before_rows:
        p = per[r[1]]
        p[0] += r[3]; p[1] += r[4]; p[2] += r[5]
    for c, i, ps in per.values():
        if i:
            k = max(1, round(ps / i))
            b[k][0] += c; b[k][1] += i
    return {k: v for k, v in b.items() if v[1] >= 1000}


def curve_ctr(cv, pos):
    if not cv:
        return None
    k = max(1, round(pos))
    best = min(cv, key=lambda x: (abs(x - k), x))
    return cv[best][0] / cv[best][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsc", required=True)
    ap.add_argument("--drop-date")
    ap.add_argument("--changes")
    ap.add_argument("--updates", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "google-updates.json"))
    ap.add_argument("--window-days", type=int, default=28)
    ap.add_argument("--drop-pct", type=float, default=15.0)
    ap.add_argument("--update-grace-days", type=int, default=3)
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--json")
    a = ap.parse_args()

    rows = read_gsc(a.gsc)
    mx = max(r[0] for r in rows)
    if a.drop_date:
        D0 = pdate(a.drop_date)
        how = "given by you"
    else:
        D0 = detect_drop_date(rows)
        if not D0:
            sys.exit("ERROR: could not find a drop date. Pass --drop-date.")
        how = "auto-detected (largest 14-day before/after fall in total clicks)"
    N = a.window_days
    one = dt.timedelta(days=1)
    b0, b1 = D0 - N * one, D0 - one
    a0, a1 = D0, min(D0 + (N - 1) * one, mx)
    if (a1 - a0).days + 1 < 7:
        sys.exit("ERROR: fewer than 7 days of data after the drop date.")
    dropf = a.drop_pct / 100.0
    changes = load_changes(a.changes)
    ref = json.load(open(a.updates))
    updates = [u for u in ref["updates"] if u.get("use_for_matching") and u.get("start") and u.get("end")]

    before_all, after_all = window(rows, b0, b1), window(rows, a0, a1)
    cv = curve(before_all)

    clusters = defaultdict(list)
    for r in rows:
        clusters[folder(r[1], a.depth)].append(r)

    sh = dt.timedelta(days=YEAR_SHIFT)
    res = []
    for name in sorted(clusters):
        cr = clusters[name]
        B, A = agg(window(cr, b0, b1)), agg(window(cr, a0, a1))
        item = dict(cluster=name, before=B, after=A)
        if B["days"] == 0 or B["clicks"] / max(B["days"], 1) * B["days"] < 30:
            item.update(verdict="TOO LITTLE DATA", confidence="n/a", matched=[], evidence=["Fewer than 30 clicks in the before window."])
            res.append(item); continue
        bpd, apd = B["clicks"] / B["days"], A["clicks"] / max(A["days"], 1)
        bi, ai = B["impressions"] / B["days"], A["impressions"] / max(A["days"], 1)
        cchg, ichg, tchg = rel(apd, bpd), rel(ai, bi), rel(A["ctr"], B["ctr"])
        pd_ = A["position"] - B["position"]
        item.update(clicks_chg=cchg, impr_chg=ichg, ctr_chg=tchg, pos_delta=pd_)
        ev = ["clicks/day %.1f -> %.1f (%+.1f%%)" % (bpd, apd, cchg * 100),
              "impressions/day %.0f -> %.0f (%+.1f%%)" % (bi, ai, ichg * 100),
              "CTR %.2f%% -> %.2f%% (%+.1f%%)" % (B["ctr"] * 100, A["ctr"] * 100, tchg * 100),
              "avg position %.2f -> %.2f (%+.2f)" % (B["position"], A["position"], pd_)]
        if cchg > -dropf:
            item.update(verdict="NO MEANINGFUL DROP", confidence="n/a", matched=[], evidence=ev)
            res.append(item); continue
        matched = {}
        # seasonal: same weekday-aligned period a year earlier
        pb = agg(window(cr, b0 - sh, b1 - sh)); pa = agg(window(cr, a0 - sh, a1 - sh))
        if pb["days"] >= N // 2 and pa["days"] >= 3 and pb["clicks"] > 0:
            pchg = rel(pa["clicks"] / pa["days"], pb["clicks"] / pb["days"])
            ev.append("same period last year: clicks/day %+.1f%%" % (pchg * 100))
            if pchg <= -dropf:
                matched["SEASONAL"] = "Last year, the same weeks fell %.1f%%." % (pchg * 100)
        else:
            ev.append("no data for the same period last year (seasonal check skipped)")
        for c in changes:
            lag = (D0 - c["date"]).days
            if 0 <= lag <= 7 and (not c["prefix"] or name.startswith(c["prefix"]) or c["prefix"].startswith(name)):
                matched["SITE CHANGE"] = "Logged change on %s (%d days before the drop): %s" % (c["date"], lag, c["note"])
                break
        if pd_ >= 1.0:
            g = dt.timedelta(days=a.update_grace_days)
            for u in updates:
                if pdate(u["start"]) <= D0 <= pdate(u["end"]) + g:
                    matched["RANKING LOSS IN UPDATE WINDOW"] = "Position worsened %.2f and the drop starts inside the %s (%s to %s)." % (pd_, u["name"], u["start"], u["end"])
                    break
        if abs(ichg) <= 0.10 and tchg <= -0.20 and abs(pd_) < 1.0:
            matched["AI OVERVIEW / SERP CHANGE"] = "Impressions steady (%+.1f%%), CTR down %.1f%%, position steady (%+.2f)." % (ichg * 100, -tchg * 100, pd_)
        if ichg <= -dropf and abs(pd_) < 1.0 and tchg > -0.20:
            matched["DEMAND DROP"] = "Impressions down %.1f%% with position steady (%+.2f)." % (-ichg * 100, pd_)
        order = ["SEASONAL", "SITE CHANGE", "RANKING LOSS IN UPDATE WINDOW", "AI OVERVIEW / SERP CHANGE", "DEMAND DROP"]
        hits = [k for k in order if k in matched]
        if not hits:
            item.update(verdict="UNEXPLAINED", confidence="LOW", matched=[], evidence=ev + ["No pattern matched."])
        else:
            item.update(verdict=hits[0], confidence="HIGH" if len(hits) == 1 else "MEDIUM", matched=hits,
                        evidence=ev + [matched[k] for k in hits])
        res.append(item)

    # clicks lost per page
    pages = defaultdict(list)
    for r in rows:
        pages[r[1]].append(r)
    page_rows = []
    for p, pr in pages.items():
        B, A = agg(window(pr, b0, b1)), agg(window(pr, a0, a1))
        if B["days"] == 0 or A["days"] == 0:
            continue
        base = B["clicks"] / B["days"] * A["days"]
        lost = max(0.0, base - A["clicks"])
        cc = curve_ctr(cv, A["position"]) if A["impressions"] else None
        short = max(0.0, A["impressions"] * cc - A["clicks"]) if cc is not None else None
        page_rows.append(dict(page=p, cluster=folder(p, a.depth), baseline=round(base, 1), actual=A["clicks"], lost=round(lost, 1),
                              curve_ctr=cc, ctr_shortfall=None if short is None else round(short, 1)))
    page_rows.sort(key=lambda x: -x["lost"])
    cl_lost = defaultdict(float)
    for x in page_rows:
        cl_lost[x["cluster"]] += x["lost"]
    for it in res:
        it["clicks_lost"] = round(cl_lost.get(it["cluster"], 0.0), 1)

    # logging anomaly note (official source only)
    note = None
    for an in ref.get("data_anomalies", []):
        s, e = pdate(an["start"]), pdate(an["end"])
        if b0 <= e and a1 >= s:
            note = an
    L = []
    L.append("# Traffic drop report")
    L.append("")
    L.append("Drop date: %s (%s). Before window: %s to %s. After window: %s to %s." % (D0, how, b0, b1, a0, a1))
    L.append(NOTICE)
    if note:
        L.append("")
        L.append("Note on data quality: Google's Search Console data anomalies page lists a logging error between %s and %s that affected %s (clicks were not affected). Your windows overlap it, so treat impression, CTR and position changes with care. Source: %s"
                 % (note["start"], note["end"], ", ".join(note["metrics_affected"]), note["source_url"]))
    L.append("")
    L.append("| Cluster | Verdict | Confidence | Clicks/day change | Clicks lost (est.) |")
    L.append("|---|---|---|---|---|")
    for it in res:
        ch = "%+.1f%%" % (it["clicks_chg"] * 100) if "clicks_chg" in it else "n/a"
        L.append("| %s | %s | %s | %s | %s |" % (it["cluster"], it["verdict"], it["confidence"], ch, "%.0f" % it["clicks_lost"]))
    L.append("")
    for it in res:
        L.append("## %s: %s (%s)" % (it["cluster"], it["verdict"], it["confidence"]))
        for e in it["evidence"]:
            L.append("- " + e)
        if len(it["matched"]) > 1:
            L.append("- Several patterns fit. Chosen by precedence: %s. Also consistent with: %s." % (it["matched"][0], ", ".join(it["matched"][1:])))
        L.append("")
    L.append("## Clicks lost per page (estimate)")
    L.append("")
    L.append("Lost = clicks per day before the drop x days in the after window, minus actual clicks. The shortfall column compares actual clicks with what the site's own before-period CTR curve gives at the page's new position. These are estimates, not measured loss.")
    L.append("")
    L.append("| Page | Baseline clicks | Actual clicks | Est. clicks lost | CTR shortfall vs site curve |")
    L.append("|---|---|---|---|---|")
    for x in page_rows:
        L.append("| %s | %.0f | %.0f | %.0f | %s |" % (x["page"], x["baseline"], x["actual"], x["lost"], "n/a" if x["ctr_shortfall"] is None else "%.0f" % x["ctr_shortfall"]))
    text = "\n".join(L) + "\n"
    print(text)
    if a.out:
        open(a.out, "w").write(text)
    if a.json:
        def clean(o):
            return json.loads(json.dumps(o, default=str))
        json.dump(clean(dict(drop_date=D0, clusters=res, pages=page_rows)), open(a.json, "w"), indent=2)


if __name__ == "__main__":
    main()
