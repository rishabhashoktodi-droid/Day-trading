#!/usr/bin/env python3
"""The Earnings Analyst, India (NSE) edition, for trader-analyst-india. Standard library only.

    python3 facts.py MARICO.NS                 # quarters, margins, YoY, TTM, NSE filings, next results date
    python3 facts.py MARICO.NS --quarters 8 --json
    python3 facts.py ANGELONE.NS CDSL.NS       # several, one after another

What it reads:
  1. Yahoo Finance's fundamentals time series for the .NS ticker (unofficial,
     free, consolidated figures in INR as Yahoo reports them): quarterly and
     annual revenue, gross profit, operating income, EBITDA, net income
     (to common shareholders) and diluted EPS.
     https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/<T>.NS?type=...
  2. NSE's official filings feeds (nsearchives.nseindia.com/content/RSS/):
     today's announcements (results, board outcomes, investor presentations,
     earnings-call schedules), the latest financial-results filings and
     upcoming board meetings, matched to the company by name.

What it says, plainly: each quarter's revenue, gross / operating / net margin,
net income and diluted EPS, each against the same quarter a year earlier, and
the trailing twelve months. Amounts print in rupees crore (1 crore = 1,00,00,000).

Yahoo lags the exchange: a quarter the company filed on NSE yesterday can be
missing for days. The tool says when the newest quarter on Yahoo is older than
the latest results the company has filed or was due to file (SEBI: within 45
days of a quarter's end, 60 for the March year-end quarter), and points you to
the NSE filing. The filing is the source of truth.

Numbers are what the company reported. They do not say what the price will
do next. Not advice.
"""

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trader-news-india"))
try:
    import news as NEWS  # NSE feed reader and the name -> ticker map
except ImportError:  # pragma: no cover
    NEWS = None

YAHOO_UA = "Mozilla/5.0 (compatible; day-trader-skill/2.0; +https://github.com/Jakeschincariol/day-trader-skill)"
TS_URL = ("https://%s.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/%s"
          "?type=%s&period1=%d&period2=%d")
FIELDS = ("TotalRevenue", "GrossProfit", "OperatingIncome", "EBITDA", "NetIncomeCommonStockholders",
          "NetIncome", "DilutedEPS")
CRORE = 1e7
IST = _dt.timedelta(hours=5, minutes=30)


class FactsError(Exception):
    pass


def http_get(url, ua=YAHOO_UA, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_series(sym, offline=None):
    """{'quarterly': {field: {date: value}}, 'annual': {...}}"""
    if offline:
        p = os.path.join(offline, "ts-%s.json" % sym)
        if not os.path.exists(p):
            raise FactsError("offline: no ts-%s.json" % sym)
        text = open(p, encoding="utf-8").read()
    else:
        types = ",".join(["quarterly" + f for f in FIELDS] + ["annual" + f for f in FIELDS])
        now = int(time.time())
        q = urllib.parse.quote(sym, safe=".-^=")
        text, last = None, None
        for host in ("query2", "query1"):
            try:
                text = http_get(TS_URL % (host, q, types, now - 4 * 366 * 86400, now + 86400))
                break
            except urllib.error.HTTPError as e:
                last = "HTTP %d" % e.code
                if e.code == 429:
                    time.sleep(5)
            except (urllib.error.URLError, OSError) as e:
                last = str(getattr(e, "reason", e))
        if text is None:
            raise FactsError("Yahoo's fundamentals answered %s for %s" % (last, sym))
    try:
        res = json.loads(text)["timeseries"]["result"] or []
    except (ValueError, KeyError, TypeError):
        raise FactsError("Yahoo's fundamentals answer for %s is not the shape this tool knows" % sym)
    out = {"quarterly": {}, "annual": {}, "currency": None}
    for r in res:
        typ = (r.get("meta") or {}).get("type", [""])[0]
        for period in ("quarterly", "annual"):
            if typ.startswith(period):
                f = typ[len(period):]
                for x in r.get(typ) or []:
                    if x and x.get("reportedValue"):
                        out[period].setdefault(f, {})[x["asOfDate"]] = float(x["reportedValue"]["raw"])
                        out["currency"] = out["currency"] or x.get("currencyCode")
    if not out["quarterly"] and not out["annual"]:
        raise FactsError("Yahoo has no reported figures for %s (check the ticker, e.g. MARICO.NS)" % sym)
    return out


def quarter_label(d):
    """'2026-06-30' -> 'Q1 FY27 (Jun-2026)': India's fiscal year runs April to March."""
    y, m = int(d[:4]), int(d[5:7])
    fq = {6: 1, 9: 2, 12: 3, 3: 4}.get(m)
    fy = y + 1 if m >= 4 else y
    mon = _dt.date(y, m, 1).strftime("%b")
    return ("Q%d FY%02d (%s-%d)" % (fq, fy % 100, mon, y)) if fq else d


def prev_year(d):
    return "%d%s" % (int(d[:4]) - 1, d[4:])


def net_income(qs, d):
    for f in ("NetIncomeCommonStockholders", "NetIncome"):
        v = qs.get(f, {}).get(d)
        if v is not None:
            return v
    return None


def analyze(series, quarters=5):
    qs = series["quarterly"]
    dates = sorted(set().union(*[set(v) for v in qs.values()])) if qs else []
    rows = []
    for d in dates:
        rev = qs.get("TotalRevenue", {}).get(d)
        ni = net_income(qs, d)
        gp, op, eps = qs.get("GrossProfit", {}).get(d), qs.get("OperatingIncome", {}).get(d), qs.get("DilutedEPS", {}).get(d)
        row = {"date": d, "quarter": quarter_label(d), "revenue": rev, "gross_profit": gp, "operating_income": op,
               "net_income": ni, "eps": eps,
               "gross_margin": gp / rev * 100 if gp is not None and rev else None,
               "operating_margin": op / rev * 100 if op is not None and rev else None,
               "net_margin": ni / rev * 100 if ni is not None and rev else None}
        py = prev_year(d)
        for k, src in (("revenue", "TotalRevenue"), ("eps", "DilutedEPS")):
            base = qs.get(src, {}).get(py)
            row[k + "_yoy"] = (row[k] / base - 1) * 100 if row[k] is not None and base and base > 0 else None
        base = net_income(qs, py)
        row["net_income_yoy"] = (ni / base - 1) * 100 if ni is not None and base and base > 0 else None
        rows.append(row)
    # trailing twelve months: the last four quarters, only when they are consecutive
    ttm = None
    if len(dates) >= 4:
        last4 = dates[-4:]
        ds = [_dt.date.fromisoformat(x) for x in last4]
        if all(80 <= (ds[i + 1] - ds[i]).days <= 100 for i in range(3)):
            ttm = {"through": last4[-1]}
            for k, f in (("revenue", "TotalRevenue"), ("eps", "DilutedEPS")):
                vals = [qs.get(f, {}).get(x) for x in last4]
                ttm[k] = sum(vals) if None not in vals else None
            vals = [net_income(qs, x) for x in last4]
            ttm["net_income"] = sum(vals) if None not in vals else None
            ttm["net_margin"] = ttm["net_income"] / ttm["revenue"] * 100 if ttm["net_income"] and ttm["revenue"] else None
    return rows[-quarters:], ttm


def latest_due_quarter(today):
    """The most recent quarter end whose results deadline (45 days, 60 for March) has passed."""
    ends = []
    for y in (today.year - 1, today.year):
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            ends.append(_dt.date(y, m, d))
    due = [e for e in ends if e + _dt.timedelta(days=60 if e.month == 3 else 45) <= today]
    return max(due) if due else None


def nse_filings(sym, offline=None):
    """(results-type filings today, upcoming board meetings) from NSE's feeds for this company."""
    if NEWS is None:
        return [], [], "the NSE feed reader (trader-news-india/news.py) is missing"
    try:
        f = NEWS.Fetcher(offline, pause=0 if offline else 0.4)
        by_name, names = NEWS.name_map(f)
        items = NEWS.match(NEWS.collect(f, feeds=("Online_announcements", "Financial_Results", "Board_Meetings")),
                           by_name, [sym])
    except Exception as e:  # a feed problem must not hide the numbers
        return [], [], "NSE feeds: %s" % e
    mine = [it for it in items if it["yours"]]
    res = [it for it in mine if it["tag"] in ("results", "analyst", "press_release") and it["feed"] != "Board_Meetings"]
    meets = [it for it in mine if it["feed"] == "Board_Meetings"]
    return res, meets, None


def cr(x):
    return "--" if x is None else "{:,.0f}".format(x / CRORE)


def pct(x):
    return "--" if x is None else "%+.1f%%" % x


def mg(x):
    return "--" if x is None else "%.1f%%" % x


def report(sym, rows, ttm, filings, meets, note, today, currency):
    out = ["%s: reported results (Yahoo fundamentals, consolidated, %s; amounts in ₹ crore)" % (sym, currency or "INR")]
    if not rows:
        out.append("  Yahoo has no quarterly figures for it.")
    else:
        out.append("  %-20s %9s %7s %7s %7s %7s %9s %7s %7s %7s" % (
            "quarter", "revenue", "YoY", "gross", "op", "net", "net inc", "YoY", "EPS", "YoY"))
        for r in rows:
            out.append("  %-20s %9s %7s %7s %7s %7s %9s %7s %7s %7s" % (
                r["quarter"], cr(r["revenue"]), pct(r["revenue_yoy"]), mg(r["gross_margin"]), mg(r["operating_margin"]),
                mg(r["net_margin"]), cr(r["net_income"]), pct(r["net_income_yoy"]),
                "--" if r["eps"] is None else "%.2f" % r["eps"], pct(r["eps_yoy"])))
        if ttm:
            out.append("  Trailing 12 months to %s: revenue ₹%s cr, net income ₹%s cr (net margin %s), diluted EPS %s."
                       % (quarter_label(ttm["through"]), cr(ttm["revenue"]), cr(ttm["net_income"]), mg(ttm["net_margin"]),
                          "--" if ttm["eps"] is None else "%.2f" % ttm["eps"]))
        latest = rows[-1]["date"]
        due = latest_due_quarter(today)
        filed_now = [f for f in filings if f["tag"] == "results"]
        if (due and _dt.date.fromisoformat(latest) < due) or filed_now:
            out.append("  Yahoo's newest quarter is %s. %s Read the NSE filing for the newest numbers; Yahoo can lag days."
                       % (quarter_label(latest),
                          "The company filed results on NSE today (below)." if filed_now else
                          "Results for %s were due by now (SEBI: 45 days after the quarter, 60 for March)." % quarter_label(due.isoformat())))
        gaps = [r["quarter"] for r in rows if r["revenue"] is None]
        if gaps:
            out.append("  Missing on Yahoo: %s." % ", ".join(gaps))
    if filings:
        out.append("  NSE filings today:")
        for f in filings[:8]:
            out.append("    %s [%s] %s: %s" % (NEWS.fmt_time(f["time"]), f["tag"], f["subject"] or f["feed"], f["text"][:150]))
            if f["link"].startswith("http") and "companies-listing" not in f["link"]:
                out.append("      " + f["link"])
    if meets:
        out.append("  Upcoming board meetings (NSE):")
        for m in meets[:4]:
            out.append("    %s" % m["text"][:180])
    if note:
        out.append("  note: " + note)
    out.append("  YoY compares a quarter with the same quarter a year earlier. These are reported figures, "
               "not a forecast and not advice.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Earnings Analyst, India edition (trader-analyst-india).")
    ap.add_argument("tickers", nargs="+", help="NSE tickers like MARICO.NS (a bare MARICO gets .NS)")
    ap.add_argument("--quarters", type=int, default=5)
    ap.add_argument("--no-nse", action="store_true", help="skip NSE's filing feeds")
    ap.add_argument("--offline", metavar="DIR", help="ts-<T>.json and the NSE feed files from DIR")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    today = (_dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None) + IST).date()
    docs, rc = [], 0
    for t in a.tickers:
        sym = t.upper() if "." in t else t.upper() + ".NS"
        try:
            series = fetch_series(sym, a.offline)
        except FactsError as e:
            print("facts.py: %s" % e, file=sys.stderr)
            rc = 1
            continue
        rows, ttm = analyze(series, a.quarters)
        filings, meets, note = ([], [], None) if a.no_nse else nse_filings(sym, a.offline)
        if a.json:
            docs.append({"symbol": sym, "currency": series["currency"], "quarters": rows, "ttm": ttm,
                         "nse_filings": filings, "board_meetings": meets, "note": note})
        else:
            print(report(sym, rows, ttm, filings, meets, note, today, series["currency"]))
            print()
        time.sleep(0.4)
    if a.json:
        print(json.dumps(docs, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
