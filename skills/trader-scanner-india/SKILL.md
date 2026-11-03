---
name: trader-scanner-india
description: 'Chart Scanner, India (NSE) edition. Scans NSE charts for setups: opening-range breakouts, bull flags, oversold bounces. Times in IST, session 9:15 AM to 3:30 PM, NSE holiday list, every day trade flat by 3:15 PM so no new entries after 3:15. Symbols keep their Yahoo suffix as typed (RELIANCE.NS, M&M.NS). Pre-market scan of daily closes (20-day closing-high breakout, bull flag, reclaimed the 20-day average, oversold, oversold bounce) and an intraday opening-range breakout scan on 5-minute bars; writes trader/watchlist.json. Free Yahoo data. Use when the user wants to scan Indian / NSE stocks or gives a .NS ticker.'
argument-hint: "[universe | daily | orb] [--symbols RELIANCE.NS,...] [--at HH:MM]"
---

# trader-scanner-india

The US trader-scanner rebuilt for India's NSE. The setup rules and data source are unchanged. What differs:

| | US trader-scanner | this edition |
| --- | --- | --- |
| clock | New York (ET, with DST) | India Standard Time (IST, UTC+5:30, no DST) |
| session | 9:30 AM to 4:00 PM | 9:15 AM to 3:30 PM |
| holidays | NYSE list + 1:00 PM early closes | NSE capital market list (2026), no early closes |
| new entries | until `no_entries_after` (15:30) | until 3:15 PM: every day trade is flat by 3:15 (`flat_by`, a config `no_entries_after` can only make it earlier; `--until` overrides) |
| symbols | BRK.B sent to Yahoo as BRK-B | kept exactly as typed: RELIANCE.NS, BAJAJ-AUTO.NS; M&M.NS is URL-encoded |
| universe | Nasdaq Trader lists | NSE `EQUITY_L.csv`, EQ series, written as SYMBOL.NS |
| prices | $ | ₹ |

`~/.claude/skills/trader-scanner-india` below is this skill's folder.

```bash
python3 "~/.claude/skills/trader-scanner-india/scan.py" daily --symbols RELIANCE.NS,TCS.NS,INFY.NS
python3 "~/.claude/skills/trader-scanner-india/scan.py" orb --symbols RELIANCE.NS,TCS.NS   # after 9:35 AM IST
python3 "~/.claude/skills/trader-scanner-india/scan.py" orb --at 10:00                       # cut the clock at 10:00 AM IST
python3 "~/.claude/skills/trader-scanner-india/scan.py" universe                            # NSE equity list -> trader/universe.txt
python3 "~/.claude/skills/trader-scanner-india/scan.py" universe --offline EQUITY_L.csv     # a file you downloaded yourself
```

Flags as in the US edition: `--min-price 5` (rupees) and `--min-volume` (daily
1,000,000 shares, orb 0), `--or-minutes 15`, `--max-confirm 200`,
`--now "2026-11-03 10:00"` (IST), `--offline PATH`, `--no-write`, `--show N`,
`--json`. Exit 0 when the scan found something, 1 when not.

With a 15-minute range (9:15, 9:20, 9:25 bars) the first bar after the range
closes at 9:35 AM IST, so `orb` runs from then until 3:15 PM IST.

## Calendar

`NSE_HOLIDAYS` in scan.py holds NSE's 2026 weekday holidays (circular
NSE/CMTR/71775 of 12 Dec 2025, plus 15 Jan 2026 from NSE/CMTR/72260). NSE had
not published its 2027 list when this was written: for a 2027 date the scan
prints a note and treats only weekends as closed. Add the 2027 dates and 2027
to `CALENDAR_YEARS` once NSE publishes them. Muhurat trading (Diwali, a special
evening session) is not modelled.

## Steps

1. Before the open: `scan.py daily --symbols ...` (or `universe` once, then
   `daily`). Tell the user the counts and the top few by setup.
2. After 9:35 AM IST: `scan.py orb`. Say how many usable charts broke their
   range and when.
3. The user picks one chart. Never pick for them. The other trader-* skills
   are still the US editions (New York clock, NYSE calendar): say so before
   handing an NSE ticker on.

## Rules

- Say what was scanned: how many symbols, how many charts came back, how many
  were usable, and the time of the data.
- Say "matched a rule", never "a buy", "a winner" or "a good trade".
- Never print a P&L, a return or a profit figure.
- A hit is stale once the price has moved on. Re-run before acting on it.

## What it never does

It never places, sizes or checks an order, never says which stock to buy,
never calls data real time, and never promises that a setup works.

## Safety

- Education and tooling, not financial advice. A PASS is a rules check, not a recommendation.
- Paper trading by default (`"paper": true`). Going live is the user's own decision, in their own config.
- Nothing in this pack places an order except trader-broker, and only when all three hold: trader-risk
  passed that exact order today, the user typed an explicit yes for that one order in the chat, and the
  user clicked Allow once on Claude's own card because the order tool is set to "Needs approval"
  (Customize > Connectors > tool permissions). Never set an order tool to "Always allow".
- No options, margin, short selling or leverage unless the config allows it and the user confirms.
- Broker keys live in environment variables or the Claude Desktop config, never in the chat.
