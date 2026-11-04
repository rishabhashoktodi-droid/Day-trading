#!/usr/bin/env python3
"""Offline checks for the India (NSE) editions of the trader-* skills.

    python3 ~/.claude/skills/tests_india.py -v
"""
import datetime as dt
import importlib.util
import json
import os
import sys
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))


def load(skill, script, name=None):
    path = os.path.join(HERE, skill, script)
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name or skill.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENTRY = load("trader-entry-india", "entry.py")
EXIT = load("trader-exit-india", "exit.py")
BUDGET = load("trader-budget-india", "size.py")
RISK = load("trader-risk-india", "check.py")
ALERTS = load("trader-alerts-india", "alerts.py")
BROKER = load("trader-broker-india", "ticket.py")
NEWS = load("trader-news-india", "news.py", "news")
FACTS = load("trader-analyst-india", "facts.py")
TM = load("trader-timemachine-india", "timemachine.py")

UTC_0345 = dt.datetime(2026, 11, 3, 3, 45)  # 9:15 IST


class Clock(unittest.TestCase):
    def test_ist_everywhere(self):
        for m in (ENTRY, EXIT, BUDGET, RISK, ALERTS, BROKER, TM):
            self.assertEqual(m.to_eastern(UTC_0345), dt.datetime(2026, 11, 3, 9, 15), m.__name__)
            self.assertEqual(m.to_eastern(dt.datetime(2026, 6, 1, 0, 0)), dt.datetime(2026, 6, 1, 5, 30), m.__name__)
        for m in (ENTRY, EXIT, BUDGET, RISK, ALERTS, BROKER):
            self.assertEqual(m.eastern_to_utc(dt.datetime(2026, 11, 3, 9, 15)), UTC_0345, m.__name__)

    def test_session_and_holidays(self):
        for m in (ENTRY, EXIT, ALERTS):
            self.assertEqual(m.session(dt.date(2026, 11, 3)), (dt.time(9, 15), dt.time(15, 30)), m.__name__)
            self.assertIsNone(m.session(dt.date(2026, 11, 10)), m.__name__)       # Diwali Balipratipada
            self.assertIsNotNone(m.session(dt.date(2026, 11, 26)), m.__name__)    # US Thanksgiving: NSE open
            self.assertEqual(m.session(dt.date(2026, 11, 27))[1], dt.time(15, 30), m.__name__)  # no US early close
        for m in (ENTRY, RISK, ALERTS):
            ok, why = m.trading_day(dt.date(2026, 1, 26))
            self.assertFalse(ok)
            self.assertIn("NSE holiday", why)
        self.assertEqual(len(RISK.NSE_HOLIDAYS), 16)

    def test_flat_by_defaults(self):
        self.assertEqual(EXIT.DEFAULTS["flat_by"], "15:15")
        self.assertEqual(RISK.DEFAULTS["flat_by"], "15:15")
        self.assertEqual(RISK.DEFAULTS["no_entries_after"], "15:15")
        self.assertEqual(BUDGET.DEFAULTS["flat_by"], "15:15")
        self.assertEqual(TM.FLAT_BY_MIN, 15 * 60 + 15)
        self.assertEqual(TM.SESSION_BARS, 72)


class Symbols(unittest.TestCase):
    def test_kept_as_typed(self):
        self.assertEqual(ENTRY.yahoo_symbol("bajaj-auto.ns"), "BAJAJ-AUTO.NS")
        self.assertEqual(ENTRY.yahoo_symbol("M&M.NS"), "M%26M.NS")
        self.assertIn("/chart/RELIANCE.NS?", ALERTS.yahoo_url("RELIANCE.NS"))
        self.assertIn("/chart/M%26M.NS?", TM.chart_url("M&M.NS"))

    def test_risk_accepts_nse(self):
        for t in ("RELIANCE.NS", "M&M.NS", "BAJAJ-AUTO.NS", "360ONE.NS", "TECHNOCRAF.NS", "TCS"):
            self.assertTrue(RISK.TICKER.match(t), t)
        self.assertFalse(RISK.TICKER.match("reliance.ns"))


class Rupees(unittest.TestCase):
    def test_money(self):
        self.assertTrue(EXIT.money(1234.5).startswith("₹"))
        self.assertTrue(BUDGET.money(1234.5).startswith("₹"))
        self.assertTrue(RISK.money(97.5).startswith("₹"))
        for k in ("max_loss_per_trade_inr", "max_daily_loss_inr", "max_order_inr", "min_order_inr"):
            self.assertIn(k, RISK.DEFAULTS)
            self.assertIn(k, BUDGET.DEFAULTS)

    def test_broker_offset_and_manual_ticket(self):
        self.assertEqual(BROKER.ny_iso(UTC_0345), "2026-11-03T09:15:00+05:30")
        steps = "\n".join(BROKER.manual_steps({"symbol": "ANGELONE.NS", "side": "buy", "qty": "25", "type": "market",
                                               "order_class": "bracket", "stop_loss_stop_price": "295.55",
                                               "take_profit_limit_price": "307.25"}, True))
        self.assertIn("BUY 25 ANGELONE, MARKET", steps)
        self.assertIn("SL-M, trigger 295.55", steps)
        self.assertIn("LIMIT 307.25", steps)
        self.assertIn("PAPER", steps)


class Zerodha(unittest.TestCase):
    def test_costs_round_trip(self):
        # 6 CDSL at 1290.80 out at 1274.30: brokerage 0.03% (under Rs 20) each side, STT, exchange, SEBI, stamp, GST
        c = BROKER.zerodha_costs(6, 1290.80, 1274.30)
        self.assertTrue(7.5 < c < 9.0, c)
        self.assertLessEqual(BROKER.zerodha_costs(1000, 1000.0, 1000.0) - BROKER.zerodha_costs(999, 1000.0, 1000.0), 3)

    def test_kite_ticket(self):
        order = {"symbol": "CDSL.NS", "side": "buy", "qty": "6", "type": "market", "order_class": "bracket",
                 "stop_loss_stop_price": "1274.30", "take_profit_limit_price": "1323.80", "plan": {"entry_plan": 1290.80}}
        t = "\n".join(BROKER.manual_steps(order, True, "zerodha"))
        self.assertIn("Intraday (MIS)", t)
        self.assertIn("SL-M, trigger 1274.30", t)
        self.assertIn("price 1273.80", t)      # SL fallback: 5 ticks of 0.10 under the trigger
        self.assertIn("Limit, price 1323.80", t)
        self.assertIn("3:25 PM", t)


class Ticks(unittest.TestCase):
    def test_bands(self):
        for p, t in ((133, "0.01"), (299.45, "0.05"), (1290.8, "0.10"), (5490, "0.50"), (12000, "1.00"), (25000, "5.00")):
            self.assertEqual(EXIT.tick_size(p), Decimal(t), p)

    def test_stop_and_target_on_tick(self):
        c = EXIT.compute(1290.80, "or_mid", None, "r", Decimal(2), or_high=1288.00, or_low=1260.61)
        self.assertEqual(c["stop"], Decimal("1274.30"))       # 1274.305 down to the 0.10 tick
        self.assertEqual(c["target"] % Decimal("0.10"), 0)
        c = EXIT.compute(299.45, "or_mid", None, "r", Decimal(2), or_high=298.80, or_low=292.35)
        self.assertEqual(c["stop"], Decimal("295.55"))
        self.assertEqual(c["target"], Decimal("307.25"))


class News(unittest.TestCase):
    def test_names_and_times(self):
        self.assertEqual(NEWS.norm_name("ASTRAL LIMITED"), NEWS.norm_name("Astral Ltd."))
        self.assertEqual(NEWS.parse_ist("03-Nov-2026 17:50:12"), dt.datetime(2026, 11, 3, 12, 20, 12))
        self.assertEqual(NEWS.classify("Outcome of Board Meeting | results for the quarter")[0], "results")
        self.assertEqual(NEWS.classify("Spurt in Volume | Significant increase in volume")[0], "exchange_query")
        self.assertEqual(NEWS.classify("Copy of Newspaper Publication | AGM notice")[0], "routine")

    def test_feed(self):
        xml = ("<rss><channel><item><title>Angel One Limited</title><link>https://nsearchives.nseindia.com/x.pdf</link>"
               "<description>Angel One Limited has informed the Exchange about Outcome |SUBJECT: Outcome of Board Meeting"
               "</description><pubDate>03-Nov-2026 17:50:12</pubDate></item></channel></rss>")
        items = NEWS.match(NEWS.parse_feed(xml, "Online_announcements"), {"angel one": "ANGELONE.NS"}, ["ANGELONE.NS"])
        self.assertEqual(items[0]["symbol"], "ANGELONE.NS")
        self.assertTrue(items[0]["yours"])
        self.assertEqual(items[0]["tag"], "results")
        self.assertTrue(items[0]["important"])


class Analyst(unittest.TestCase):
    def test_fiscal_quarters(self):
        self.assertEqual(FACTS.quarter_label("2026-06-30"), "Q1 FY27 (Jun-2026)")
        self.assertEqual(FACTS.quarter_label("2026-03-31"), "Q4 FY26 (Mar-2026)")
        self.assertEqual(FACTS.latest_due_quarter(dt.date(2026, 11, 3)), dt.date(2026, 6, 30))
        self.assertEqual(FACTS.latest_due_quarter(dt.date(2026, 11, 14)), dt.date(2026, 9, 30))

    def test_yoy_and_ttm(self):
        q = {"TotalRevenue": {}, "NetIncomeCommonStockholders": {}, "DilutedEPS": {}}
        for i, d in enumerate(["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]):
            q["TotalRevenue"][d] = 100.0 + 10 * i
            q["NetIncomeCommonStockholders"][d] = 10.0 + i
            q["DilutedEPS"][d] = 1.0 + 0.1 * i
        rows, ttm = FACTS.analyze({"quarterly": q, "annual": {}}, 5)
        self.assertAlmostEqual(rows[-1]["revenue_yoy"], 40.0)
        self.assertAlmostEqual(ttm["revenue"], 110 + 120 + 130 + 140)


class Nov4Improvements(unittest.TestCase):
    """From the 4 Nov 2026 ANGELONE review: OR-low stop default, close-only breakouts, drawdown everywhere."""

    def test_exit_default_stop_is_or_low(self):
        import types
        a = types.SimpleNamespace(stop=None)
        # build_plan picks the default; check the resolver directly and the default text
        self.assertEqual(EXIT.parse_stop("or-low"), ("or_low", None))
        src = open(os.path.join(HERE, "trader-exit-india", "exit.py"), encoding="utf-8").read()
        self.assertIn('stop_text = "or-low"', src)
        c = EXIT.compute(311.45, "or_low", None, "r", Decimal(1), or_high=310.20, or_low=307.30)
        self.assertEqual(c["stop"], Decimal("307.30"))
        lines = EXIT.stop_tradeoff({"entry": 311.45, "stop_rule": "or_low",
                                    "opening_range": {"high": 310.20, "low": 307.30}})
        self.assertIn("OR low", lines[0])
        self.assertIn("308.75", lines[0])      # the midpoint alternative is shown

    def _chart(self, bars):
        day = dt.date(2026, 11, 4)
        ts, o, h, l, c, v = [], [], [], [], [], []
        for k, (hi, lo, cl) in enumerate(bars):
            t = dt.datetime.combine(day, dt.time(9, 15)) + dt.timedelta(minutes=5 * k)
            ts.append(int((ENTRY.eastern_to_utc(t) - dt.datetime(1970, 1, 1)).total_seconds()))
            o.append(cl); h.append(hi); l.append(lo); c.append(cl); v.append(1000)
        return {"chart": {"result": [{"meta": {"symbol": "TEST.NS"}, "timestamp": ts,
                "indicators": {"quote": [{"open": o, "high": h, "low": l, "close": c, "volume": v}]}}]}}

    def test_entry_wick_is_false_breakout(self):
        bars = [(100, 98, 99), (100, 98.5, 99.5), (99.8, 98.8, 99.2),   # range 98-100
                (101, 99, 99.9),                                       # wick above, closes inside
                (100.6, 99.5, 100.4)]                                  # closes above: the trigger
        now = ENTRY.eastern_to_utc(dt.datetime(2026, 11, 4, 9, 45))
        chart = self._chart(bars)
        res = ENTRY.evaluate(ENTRY.parse_chart(json.dumps(chart), "TEST.NS"), now)
        self.assertEqual(res["status"], "triggered")
        self.assertEqual(res["trigger"]["bar_start"], "09:35")
        self.assertEqual([f["bar_start"] for f in res["false_breakouts"]], ["09:30"])

    def test_timemachine_drawdown(self):
        # a flat pool: every bar dips 1% then closes flat
        pool = [[(1.0, 1.0, 0.99, 1.0)] for _ in range(TM.SESSION_BARS)]
        mc = TM.simulate(pool, 100.0, 98.0, 102.0, 3, 20, replays=200, seed=19, window=0)
        dd = mc["drawdown"]["all"]
        self.assertAlmostEqual(dd["median_worst"], 99.0, places=2)
        self.assertAlmostEqual(dd["median_depth"], 0.5, places=3)
        self.assertEqual(mc["p_neither"], 1.0)

    def test_alerts_drawdown(self):
        rules = [{"id": "x-dd", "symbol": "ANGELONE.NS", "type": "drawdown", "entry": 310.80, "stop": 308.75, "frac": 0.5}]
        status = {"date": "2026-11-04", "open": True, "opens": "09:15", "closes": "15:30", "now_new_york": "11:00"}
        now = ALERTS.eastern_to_utc(dt.datetime(2026, 11, 4, 11, 0))
        q = lambda p: {"ANGELONE.NS": {"price": p}}
        rings, st = ALERTS.evaluate(rules, q(309.90), status, {}, now)   # halfway is 309.775: not yet
        self.assertEqual(rings, [])
        rings, st = ALERTS.evaluate(rules, q(309.70), status, st, now)
        self.assertEqual(len(rings), 1)
        self.assertIn("Trade under pressure: approaching stop zone", rings[0]["message"])
        rings, st = ALERTS.evaluate(rules, q(309.50), status, st, now)   # rings once
        self.assertEqual(rings, [])
        plan_rules = ALERTS.rules_from_plan({"symbol": "ANGELONE.NS", "entry": 311.45, "stop": 307.30,
                                             "target": 315.60, "date": "2026-11-04"})
        self.assertIn("drawdown", [r["type"] for r in plan_rules])


if __name__ == "__main__":
    unittest.main()
