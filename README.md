# Day-trading: NSE (India) edition of the trader-* Claude skills

Ten Claude Code skills for intraday trading on the **National Stock Exchange of India**, adapted from the
US `trader-*` skill pack:

- IST clock (UTC+5:30)
- NSE session 9:15 AM–3:30 PM
- NSE holiday list
- every day trade flat by **3:15 PM**
- prices in **₹**, rounded to NSE tick sizes
- tickers kept as typed (`RELIANCE.NS`, `M&M.NS`, `BAJAJ-AUTO.NS`)

> Education and tooling, not financial advice. Paper trading is the default. Most people who day trade
> lose money; a scan, a simulation or a risk PASS does not change that.

## The skills, in the order of a trading day (IST)

| When | Skill | What it does |
| --- | --- | --- |
| Evening before / by 9:00 | `trader-scanner-india` | Scans NSE stocks (daily closes) for 20-day breakouts, bull flags, MA reclaims, oversold bounces → `trader/watchlist.json` |
| | `trader-news-india` | NSE's official filings feeds (announcements, results, board meetings, dividends) for your tickers, tagged, new items only |
| | `trader-analyst-india` | Quarterly revenue, margins, net income, EPS in ₹ crore, YoY, TTM (Yahoo fundamentals + NSE filings) |
| 9:15–9:30 | (wait) | The 15-minute opening range forms |
| From 9:35 | `trader-entry-india` | Bar by bar: the first 5-minute bar to close above the opening-range high |
| At the signal | `trader-exit-india` | Stop (range midpoint by default) and target (2R), on the NSE tick |
| | `trader-timemachine-india` | 10,000 replays plus the 60-day history of the same rule: target first, stop first, or neither by 3:15 |
| | `trader-budget-india` | Whole shares inside your ₹ max loss, position cap and cash |
| | `trader-risk-india` | PASS / BLOCK: stop required, ₹ limits per trade and per day, trades per day, entry window, NSE holidays |
| | `trader-broker-india` | A ticket to enter yourself in your broker's app (BUY, SL-M stop-loss, LIMIT target, Intraday/MIS). Claude places nothing |
| In the trade, 3:15 PM | `trader-alerts-india` | Stop / target / 3:15 flat-by alerts, the NSE clock, delayed ₹ quotes |

## Install

Copy the skill folders where Claude Code finds skills:

```bash
mkdir -p ~/.claude/skills && cp -r skills/trader-*-india ~/.claude/skills/
```

(or into a project's `.claude/skills/`). Run them from a working folder. They read and write `trader/`
there: `config.json`, `watchlist.json`, `entry.json`, `plan.json`, `orders.json`, `prices.json`, `state/`.

Then ask Claude, for example: "scan NSE for setups", "news on ANGELONE.NS", "how did MARICO's results look",
"watch CDSL.NS for the opening-range breakout".

## Config: `trader/config.json`

| key | value here | meaning |
| --- | --- | --- |
| `budget` | 10000 | account size, ₹ |
| `max_loss_per_trade_inr` | 100 | loss at the stop, per trade |
| `max_daily_loss_inr` | 200 | stop trading for the day after this (placeholder: confirm) |
| `max_trades_per_day` | 2 | placeholder: confirm |
| `cash_buffer_pct` | 5 | cash never used |
| `no_entries_before` / `no_entries_after` / `flat_by` | 09:30 / 15:15 / 15:15 | IST |
| `broker` | `zerodha` | Kite tickets you enter yourself (`manual` = any broker) |
| `paper` | `true` | paper trading |

## Data sources and limits

- **Prices:** Yahoo Finance chart and spark endpoints. Free, unofficial and delayed. Your broker's price is the one that fills.
- **News:** NSE RSS feeds on `nsearchives.nseindia.com`. The announcements feed only holds **today**, so run news daily. Media headline sites are not read.
- **Results:** Yahoo fundamentals time series. These **lag NSE by days** after a results filing, and the tool says so and links the filing.
- **Universe:** NSE `EQUITY_L.csv`, EQ series (`scan.py universe` regenerates `trader/universe.txt`).
- **Holidays:** NSE 2026 list (circulars NSE/CMTR/71775 and 72260). **Add 2027** when NSE publishes it (`NSE_HOLIDAYS` in each script).
- **Tick sizes:** NSE bands since 15 Apr 2025 (0.01 below ₹250, 0.05, 0.10, 0.50, 1, 5). The band is set from the previous month's close; the entry price stands in for it.

## Tests

```bash
cd skills && python3 tests_india.py -v && python3 trader-scanner-india/test_scan.py
```
