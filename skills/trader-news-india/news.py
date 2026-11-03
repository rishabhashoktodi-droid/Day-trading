#!/usr/bin/env python3
"""News monitor, India (NSE) edition, for trader-news-india. Standard library only.

Watches NSE's official corporate filings for the stocks you watch or hold and
prints only what is new since the last check, newest first, in India time
(IST), with how far each stock has moved today and a tag on every item.

    python3 news.py                                   # watchlist + plan + portfolio tickers
    python3 news.py --tickers ANGELONE.NS MARICO.NS
    python3 news.py --tickers TCS.NS --all            # everything in the feeds, seen or not, routine too
    python3 news.py --no-moves                        # skip the price line per ticker
    python3 news.py --market results                  # every company's results filed today, whole market

Your tickers, when --tickers is not given: every hit in trader/watchlist.json
(trader-scanner-india), the symbol in trader/plan.json (trader-exit-india) and
the positions in trader/portfolio.json.

Sources (NSE's public RSS feeds on nsearchives.nseindia.com, one request each):
  Online_announcements.xml  every company announcement filed today (results,
                            board outcomes, orders, deals, management changes,
                            analyst meets, press releases, regulatory actions)
  Financial_Results.xml     the latest results filings
  Board_Meetings.xml        upcoming board meetings (results dates)
  Corporate_action.xml      dividends, splits, bonus issues and their ex-dates
The feeds name the company, not the ticker: names are matched to tickers with
NSE's equity list (trader/universe.txt from trader-scanner-india, or
EQUITY_L.csv). Media headlines (Economic Times, Moneycontrol, Google News) are
not read: this environment's network does not reach them, and a filing is the
primary source anyway.

The move: Yahoo Finance's chart endpoint (unofficial, can lag), the last price
against yesterday's close.

State: trader/state/news.json remembers what you have seen (30 days), so an
item shows once. Offline: --offline DIR reads <Feed>.xml, chart-<TICKER>.json
and EQUITY_L.csv from DIR.

A filing is a fact the company reported; what it means for the price is not in
it. Open the filing before acting, and treat nothing here as advice.
"""

import argparse
import csv
import datetime as _dt
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NSE_RSS = "https://nsearchives.nseindia.com/content/RSS/%s.xml"
EQUITY_L = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
FEEDS = ("Online_announcements", "Financial_Results", "Board_Meetings", "Corporate_action")
CHART = "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=5m"
UA = "Mozilla/5.0 (compatible; day-trader-skill/2.0)"  # NSE times out a User-Agent that carries a URL
KEEP_DAYS = 30
MOVE_PCT = 3.0  # a stock this far from yesterday's close is flagged as moving
IST = _dt.timedelta(hours=5, minutes=30)

# (tag, pattern on "subject | description", important?) - first match wins
TAGS = [
    ("exchange_query", r"spurt in (volume|price)|price movement|clarification|significant (increase|movement)", True),
    ("results", r"financial result|outcome of board meeting|integrated filing.{0,20}financial|unaudited|audited result", True),
    ("legal", r"actions? (initiated|taken)|orders? passed|litigation|dispute|penalt|show cause|sebi order|fraud|default|insolvency|nclt|raid|search and seizure|tax demand", True),
    ("deal", r"acquisition|amalgamation|merger|scheme of arrangement|joint venture|award of order|bagging|receiving of order|order win|contract|agreement|divest|stake sale|takeover", True),
    ("management", r"change in (directors|management)|appointment|resignation|cessation|kmp|managing director|chief executive|\bceo\b|\bcfo\b", True),
    ("capital", r"fund raising|alteration of capital|buy ?back|bonus|split|preferential|\bqip\b|rights issue|allotment|warrant", True),
    ("rating", r"credit rating", True),
    ("insider", r"insider|\bsast\b|pledge|encumbrance|promoter", False),
    ("board_meeting", r"board meeting intimation|prior intimation|meeting date|to consider and approve", False),
    ("dividend", r"dividend|record date|ex-date", False),
    ("analyst", r"analyst|investor meet|investor presentation|earnings call|con\. ?cal|conference call|audio recording|transcript", False),
    ("press_release", r"press release|media release", False),
    ("routine", r"newspaper|trading window|certificate|compliance|declaration of nav|monitoring agency|"
                r"redemption|payment of interest|loss of share|duplicate share|esop|esos|notice of shareholders|"
                r"shareholders meeting|updates$|general updates|rta|registrar|deviation", False),
]


class NewsError(Exception):
    pass


# ---------------------------------------------------------------- small helpers

def now_utc():
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None, microsecond=0)


def to_ist(utc):
    return utc + IST


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, doc):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def norm_name(name):
    """'ASTRAL LIMITED' / 'Astral Ltd.' -> 'astral'."""
    s = re.sub(r"[^a-z0-9& ]", " ", (name or "").lower().replace("&amp;", "&"))
    s = re.sub(r"\b(limited|ltd|the|company|co|india|of)\b", " ", s)
    return " ".join(s.split())


def watch_from_files(portfolio="trader/portfolio.json", watchlist="trader/watchlist.json", plan="trader/plan.json"):
    out = []
    w = load_json(watchlist, {}) or {}
    for h in (w.get("hits") or []) if isinstance(w, dict) else []:
        if isinstance(h, dict) and h.get("symbol"):
            out.append(h["symbol"])
    p = load_json(plan, {}) or {}
    if isinstance(p, dict) and p.get("symbol"):
        out.append(p["symbol"])
    pf = load_json(portfolio, {}) or {}
    for pos in (pf.get("positions") or []) if isinstance(pf, dict) else []:
        if isinstance(pos, dict) and pos.get("symbol"):
            out.append(pos["symbol"])
    seen, res = set(), []
    for s in out:
        s = s.strip().upper()
        if s and s not in seen:
            seen.add(s)
            res.append(s)
    return res


# ---------------------------------------------------------------- fetching

class Fetcher:
    def __init__(self, offline=None, pause=0.4):
        self.offline, self.pause, self.n = offline, pause, 0

    def get(self, url, offline_name):
        if self.offline:
            p = os.path.join(self.offline, offline_name)
            if not os.path.exists(p):
                raise NewsError("offline: no %s" % offline_name)
            with open(p, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        if self.n and self.pause:
            time.sleep(self.pause)
        self.n += 1
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise NewsError("%s answered HTTP %d" % (urllib.parse.urlsplit(url).netloc, e.code))
        except (urllib.error.URLError, OSError) as e:
            raise NewsError("could not reach %s: %s" % (urllib.parse.urlsplit(url).netloc, getattr(e, "reason", e)))


def name_map(fetcher, universe="trader/universe.txt", equity_l="trader/nse/EQUITY_L.csv"):
    """{normalized company name: SYMBOL.NS} and {SYMBOL.NS: company name}."""
    rows = []
    if os.path.exists(universe) and not fetcher.offline:
        with open(universe, encoding="utf-8") as fh:
            for ln in fh:
                if "|" in ln:
                    sym, name = ln.rstrip("\n").split("|", 1)
                    rows.append((sym.strip().upper(), name.strip()))
    if not rows:
        if os.path.exists(equity_l) and not fetcher.offline:
            with open(equity_l, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        else:
            text = fetcher.get(EQUITY_L, "EQUITY_L.csv")
        for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            if r.get("SYMBOL"):
                rows.append((r["SYMBOL"].upper() + ".NS", r.get("NAME OF COMPANY", "")))
    by_name = {}
    for sym, name in rows:
        by_name.setdefault(norm_name(name), sym)
    return by_name, dict(rows)


# ---------------------------------------------------------------- parsing

def parse_ist(text):
    """'03-Nov-2026 17:50:12' or '02-May-2026 16:46' (IST) -> naive UTC, or None."""
    t = (text or "").strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return _dt.datetime.strptime(t, fmt) - IST
        except ValueError:
            continue
    return None


def classify(text):
    low = text.lower()
    for tag, pat, important in TAGS:
        if re.search(pat, low):
            return tag, important
    return "other", False


def parse_feed(data, feed):
    try:
        root = ET.fromstring(data.encode("utf-8") if isinstance(data, str) else data)
    except ET.ParseError as e:
        raise NewsError("NSE %s is not valid RSS: %s" % (feed, e))
    out = []
    for it in root.iter("item"):
        company = " ".join((it.findtext("title") or "").split())
        desc = " ".join((it.findtext("description") or "").split())
        link = (it.findtext("link") or "").strip()
        when = parse_ist(it.findtext("pubDate"))
        if feed == "Corporate_action":
            company = re.sub(r"\s*-\s*Ex-Date:.*$", "", company)
        subject = ""
        m = re.search(r"\|\s*SUBJECT:\s*(.+)$", desc)
        if m:
            subject = m.group(1).strip()
            desc = desc[:m.start()].strip()
        if feed == "Financial_Results":
            subject = subject or "Financial Results"
        elif feed == "Board_Meetings":
            subject = subject or "Board Meeting"
        elif feed == "Corporate_action":
            subject = subject or "Corporate Action"
        tag, important = classify("%s | %s" % (subject, desc))
        if feed == "Financial_Results":
            tag, important = "results", True
        out.append({"company": company, "subject": subject, "text": desc, "link": link, "feed": feed,
                    "time": when.strftime("%Y-%m-%dT%H:%M:%SZ") if when else None, "tag": tag,
                    "important": important})
    return out


def parse_chart(data, ticker):
    try:
        res = json.loads(data)["chart"]["result"][0]
        m = res["meta"]
        price, prev = m.get("regularMarketPrice"), m.get("chartPreviousClose") or m.get("previousClose")
        if price is None or not prev:
            return None
        return {"symbol": ticker, "price": float(price), "prev_close": float(prev),
                "pct": (float(price) / float(prev) - 1) * 100,
                "time": m.get("regularMarketTime")}
    except (ValueError, KeyError, IndexError, TypeError):
        return None


# ---------------------------------------------------------------- the run

def fingerprint(it):
    return hashlib.sha1(("%s|%s|%s|%s" % (it["company"], it["subject"], it["text"][:200], it["link"])).encode()).hexdigest()[:16]


def collect(fetcher, feeds=FEEDS, errors=None):
    items = []
    for f in feeds:
        try:
            items += parse_feed(fetcher.get(NSE_RSS % f, f + ".xml"), f)
        except NewsError as e:
            if errors is not None:
                errors.append("NSE %s: %s" % (f, e))
    seen, out = set(), []
    for it in items:
        k = fingerprint(it)
        if k not in seen:
            seen.add(k)
            it["id"] = k
            out.append(it)
    return out


def match(items, by_name, watch):
    """Attach a ticker to each item whose company is on your list."""
    wanted = set(watch)
    for it in items:
        sym = by_name.get(norm_name(it["company"]))
        it["symbol"] = sym
        it["yours"] = bool(sym and sym in wanted)
    return items


def collect_moves(fetcher, watch, errors=None):
    moves = {}
    for t in watch:
        q = urllib.parse.quote(t, safe=".-^=")
        try:
            data = fetcher.get(CHART % ("query2", q), "chart-%s.json" % t)
        except NewsError:
            try:
                data = fetcher.get(CHART % ("query1", q), "chart-%s.json" % t)
            except NewsError as e:
                if errors is not None:
                    errors.append("price %s: %s" % (t, e))
                continue
        mv = parse_chart(data, t)
        if mv:
            moves[t] = mv
    return moves


def fmt_time(stamp):
    if not stamp:
        return "--"
    t = to_ist(_dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    return t.strftime("%d %b %H:%M")


def render(items, moves, errors, now, watch, show_all, market):
    out = []
    head = "NSE filings, %s IST" % to_ist(now).strftime("%a %Y-%m-%d %H:%M")
    out.append(head + (" (whole market: %s)" % market if market else " for %d ticker%s" % (len(watch), "" if len(watch) == 1 else "s")))
    if moves:
        out.append("Moves vs yesterday's close (Yahoo, delayed):")
        for t in watch:
            m = moves.get(t)
            if m:
                flag = "  MOVING" if abs(m["pct"]) >= MOVE_PCT else ""
                out.append("  %-14s ₹%-10s %+6.2f%%%s" % (t, "{:,.2f}".format(m["price"]), m["pct"], flag))
    if not items:
        out.append("Nothing new%s." % ("" if show_all else " since your last check (--all shows everything in today's feeds)"))
    for it in items:
        star = "!" if it["important"] else " "
        who = it.get("symbol") or it["company"]
        out.append("%s %s  %-13s [%s] %s" % (star, fmt_time(it["time"]), who, it["tag"], it["subject"] or it["feed"]))
        if it["text"]:
            out.append("      " + it["text"][:220] + ("..." if len(it["text"]) > 220 else ""))
        if it["link"] and it["link"].startswith("http") and "companies-listing" not in it["link"]:
            out.append("      " + it["link"])
    for e in errors:
        out.append("note: " + e)
    out.append("! = results, deal, legal, management, capital or rating. A filing is what the company said, "
               "not what the price will do. Not advice.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NSE filings monitor (trader-news-india).")
    ap.add_argument("--tickers", nargs="*", help="Yahoo/NSE tickers like ANGELONE.NS (default: watchlist, plan, portfolio)")
    ap.add_argument("--all", action="store_true", help="show everything in today's feeds, seen or not, routine filings too")
    ap.add_argument("--market", choices=["results", "important", "board_meetings", "dividends"],
                    help="the whole market, not just your tickers")
    ap.add_argument("--no-moves", action="store_true")
    ap.add_argument("--state", default="trader/state/news.json")
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--now", help='pretend it is this IST time, "2026-11-03 18:00"')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    now = now_utc()
    if a.now:
        try:
            now = _dt.datetime.fromisoformat(a.now.strip()) - IST
        except ValueError:
            print("news.py: --now wants an IST time like \"2026-11-03 18:00\"", file=sys.stderr)
            return 1
    fetcher = Fetcher(a.offline, pause=0 if a.offline else 0.4)
    watch = [t.upper() for t in (a.tickers or [])] or watch_from_files()
    watch = [t if "." in t else t + ".NS" for t in watch]
    if not watch and not a.market:
        print("news.py: no tickers: pass --tickers ANGELONE.NS ..., or run trader-scanner-india first", file=sys.stderr)
        return 1
    errors = []
    try:
        by_name, names = name_map(fetcher)
    except NewsError as e:
        print("news.py: could not load NSE's equity list to match company names: %s" % e, file=sys.stderr)
        return 1
    missing = [t for t in watch if t not in names and t.endswith(".NS")]
    if missing:
        errors.append("not in NSE's equity list (check the spelling): " + ", ".join(missing))
    items = match(collect(fetcher, errors=errors), by_name, watch)
    if not any(it for it in items) and errors:
        print("news.py: " + "; ".join(errors), file=sys.stderr)
        return 1
    if a.market == "results":
        sel = [it for it in items if it["tag"] == "results"]
    elif a.market == "important":
        sel = [it for it in items if it["important"]]
    elif a.market == "board_meetings":
        sel = [it for it in items if it["feed"] == "Board_Meetings"]
    elif a.market == "dividends":
        sel = [it for it in items if it["feed"] == "Corporate_action"]
    else:
        sel = [it for it in items if it["yours"] and (a.all or it["tag"] != "routine")]
    state = load_json(a.state, {}) or {}
    seen = state.get("seen", {})
    if not a.all:
        sel = [it for it in sel if it["id"] not in seen]
    sel.sort(key=lambda it: it["time"] or "", reverse=True)
    moves = {} if (a.no_moves or a.market) else collect_moves(fetcher, watch, errors)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for it in sel:
        seen[it["id"]] = stamp
    cutoff = (now - _dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["seen"] = {k: v for k, v in seen.items() if v >= cutoff}
    state["last_check"] = stamp
    if not a.offline:
        save_json(a.state, state)
    if a.json:
        print(json.dumps({"as_of_ist": to_ist(now).strftime("%Y-%m-%d %H:%M"), "tickers": watch, "items": sel,
                          "moves": moves, "errors": errors}, indent=2))
    else:
        print(render(sel, moves, errors, now, watch, a.all, a.market))
    return 0


if __name__ == "__main__":
    sys.exit(main())
