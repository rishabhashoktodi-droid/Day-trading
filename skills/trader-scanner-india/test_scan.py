import datetime as dt, json, os, sys, tempfile, unittest, contextlib, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as S

def ist_ts(day, hh, mm):
    utc = S.eastern_to_utc(dt.datetime.combine(day, dt.time(hh, mm)))
    return int((utc - dt.datetime(1970, 1, 1)).total_seconds())

def bars(day, closes, highs=None):
    t = [ist_ts(day, 9, 15 + 5 * k) if 15 + 5 * k < 60 else ist_ts(day, 9 + (15 + 5 * k) // 60, (15 + 5 * k) % 60)
         for k in range(len(closes))]
    h = highs or [c + 0.5 for c in closes]
    return {"chart": {"result": [{"meta": {"symbol": "RELIANCE.NS"}, "timestamp": t,
            "indicators": {"quote": [{"close": closes, "high": h, "low": [c - 0.5 for c in closes],
                                      "open": closes, "volume": [1000] * len(closes)}]}}]}}

class T(unittest.TestCase):
    def test_ist_offset(self):
        self.assertEqual(S.to_eastern(dt.datetime(2026, 11, 3, 3, 45)), dt.datetime(2026, 11, 3, 9, 15))
        self.assertEqual(S.parse_now("2026-11-03 09:15"), dt.datetime(2026, 11, 3, 3, 45))
        self.assertEqual(S.parse_now("2026-11-03T03:45Z"), dt.datetime(2026, 11, 3, 3, 45))
        # no DST: same offset in June
        self.assertEqual(S.to_eastern(dt.datetime(2026, 6, 1, 0, 0)), dt.datetime(2026, 6, 1, 5, 30))

    def test_session_hours(self):
        self.assertEqual(S.session(dt.date(2026, 11, 3)), (dt.time(9, 15), dt.time(15, 30)))
        self.assertEqual(S.session(dt.date(2026, 11, 27)), (dt.time(9, 15), dt.time(15, 30)))  # no US early close

    def test_holidays(self):
        for d in ["2026-01-26", "2026-03-03", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25", "2026-01-15"]:
            ok, why = S.trading_day(dt.date.fromisoformat(d))
            self.assertFalse(ok, d); self.assertIn("NSE holiday", why)
        for d in ["2026-11-26", "2026-07-03", "2026-09-07"]:  # US holidays are now trading days
            self.assertTrue(S.trading_day(dt.date.fromisoformat(d))[0], d)
        self.assertEqual(S.trading_day(dt.date(2026, 11, 7))[1], "weekend")
        self.assertTrue(all(dt.date.fromisoformat(d).weekday() < 5 for d in S.NSE_HOLIDAYS))
        self.assertEqual(S.calendar_warning(dt.date(2026, 5, 5)), "")
        self.assertIn("2027", S.calendar_warning(dt.date(2027, 1, 4)))

    def test_symbols_kept(self):
        self.assertEqual(S.to_yahoo("reliance.ns"), "RELIANCE.NS")
        self.assertEqual(S.to_yahoo("BAJAJ-AUTO.NS"), "BAJAJ-AUTO.NS")
        self.assertEqual(S.to_yahoo("M&M.NS"), "M%26M.NS")
        self.assertIn("/chart/RELIANCE.NS?", S.chart_path("RELIANCE.NS", "1d", "5m"))
        self.assertIn("symbols=RELIANCE.NS,M%26M.NS&", S.spark_path(["RELIANCE.NS", "M&M.NS"], "3mo", "1d"))
        doc = {"spark": {"result": [{"symbol": "M&M.NS", "response": [{"timestamp": [1], "indicators": {"quote": [{"close": [1.0]}]}}]},
                                    {"symbol": "RELIANCE.NS", "response": [{"timestamp": [1], "indicators": {"quote": [{"close": [1.0]}]}}]}]}}
        got = S.parse_spark(doc, {S.to_yahoo(s): s for s in ["M&M.NS", "RELIANCE.NS"]})
        self.assertEqual(sorted(got), ["M&M.NS", "RELIANCE.NS"])

    def test_universe(self):
        csv = "﻿SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING\nRELIANCE,Reliance Industries Limited,EQ,29-NOV-1995\nM&M,Mahindra & Mahindra Limited,EQ,1-JAN-2000\nXYZ,Some Co,BE,1-JAN-2020\n"
        kept, counts = S.build_universe(csv)
        self.assertEqual([k for k, _ in kept], ["M&M.NS", "RELIANCE.NS"])
        self.assertEqual(counts["series BE"], 1)

    def test_orb_window(self):
        d = dt.date(2026, 11, 3)
        with self.assertRaises(S.ScanError) as e:
            S.orb_window(S.parse_now("2026-11-03 09:30"), None, 15, dt.time(15, 15))
        self.assertIn("9:15 AM to 9:30 AM", str(e.exception)); self.assertIn("IST", str(e.exception))
        self.assertEqual(S.orb_window(S.parse_now("2026-11-03 09:35"), None, 15, dt.time(15, 15)),
                         (d, dt.datetime(2026, 11, 3, 9, 35)))
        with self.assertRaises(S.ScanError) as e:
            S.orb_window(S.parse_now("2026-11-03 15:20"), None, 15, dt.time(15, 15))
        self.assertIn("3:15", str(e.exception))
        with self.assertRaises(S.ScanError) as e:
            S.orb_window(S.parse_now("2026-11-03 15:30"), None, 15, dt.time(15, 15))
        self.assertIn("closed at 3:30 PM IST", str(e.exception))
        with self.assertRaises(S.ScanError) as e:
            S.orb_window(S.parse_now("2026-11-10 11:00"), None, 15, dt.time(15, 15))
        self.assertIn("Diwali", str(e.exception))

    def test_orb_scan_offline(self):
        d = dt.date(2026, 11, 3)
        closes = [100, 101, 100.5, 101.2, 102.0, 102.5]  # range 9:15-9:25 high 101.5; 9:35 bar closes 102.0
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "RELIANCE.NS.json")
            json.dump(bars(d, closes), open(p, "w"))
            out = os.path.join(tmp, "w.json")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = S.main(["orb", "--offline", tmp, "--now", "2026-11-03 09:45", "--min-price", "0", "--out", out,
                             "--config", os.path.join(tmp, "none.json")])
            self.assertEqual(rc, 0, buf.getvalue())
            w = json.load(open(out))
            self.assertEqual(w["hits"][0]["symbol"], "RELIANCE.NS")
            self.assertEqual(w["hits"][0]["at"], "9:40 AM")
            self.assertEqual(w["as_of"], "2026-11-03 09:45 IST")
            self.assertIn("₹", buf.getvalue())

    def test_until_capped_by_flat_by(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = tmp + "-c.json"; json.dump({"no_entries_after": "15:25"}, open(cfg, "w"))
            json.dump(bars(dt.date(2026, 11, 3), [100] * 5), open(os.path.join(tmp, "RELIANCE.NS.json"), "w"))
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = S.main(["orb", "--offline", tmp, "--now", "2026-11-03 15:20", "--config", cfg, "--no-write"])
            self.assertEqual(rc, 1); self.assertIn("after 15:15", err.getvalue())

if __name__ == "__main__":
    unittest.main(verbosity=2)
