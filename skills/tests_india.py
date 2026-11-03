#!/usr/bin/env python3
"""Offline checks for the India (NSE) editions of the trader-* skills.

    python3 ~/.claude/skills/tests_india.py -v
"""
import datetime as dt
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
