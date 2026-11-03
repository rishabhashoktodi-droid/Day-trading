---
name: trader-analyst-india
description: 'The Earnings Analyst, India (NSE) edition. Sums up an NSE company''s reported results: revenue, gross / operating / net margins, net income and diluted EPS quarter by quarter in ₹ crore and Indian fiscal quarters (Q1 FY27 = Apr-Jun 2026), each against the same quarter a year earlier, plus the trailing twelve months. Pairs Yahoo''s fundamentals with NSE''s own filings (today''s results, earnings-call schedules, upcoming board meetings) and says when Yahoo lags the exchange. Reads an earnings call transcript or results PDF text you paste. Use: "how did Marico''s results look", "what changed this quarter", "is revenue growing", "when does it report" for .NS tickers.'
---

# trader-analyst-india

```bash
python3 ~/.claude/skills/trader-analyst-india/facts.py MARICO.NS
python3 ~/.claude/skills/trader-analyst-india/facts.py ANGELONE.NS CDSL.NS --quarters 8
python3 ~/.claude/skills/trader-analyst-india/facts.py TCS.NS --json
```

Flags: `--quarters N` (default 5), `--no-nse`, `--offline DIR`, `--json`.

## What it reads

1. **Yahoo Finance fundamentals time series** for the `.NS` ticker
   (unofficial, free, consolidated, INR): quarterly and annual revenue, gross
   profit, operating income, EBITDA, net income to common shareholders,
   diluted EPS. Usually about five recent quarters, sometimes with gaps.
2. **NSE's filings feeds** (via trader-news-india's reader): today's results
   filings, board-meeting outcomes, investor presentations, earnings-call
   schedules, and upcoming board meetings (the next results date).

## How to read it

- Quarters are Indian fiscal quarters: FY runs April to March, so Q1 FY27 is
  April to June 2026.
- YoY compares a quarter with the same quarter a year earlier; `--` means Yahoo
  lacks that base quarter.
- Yahoo lags the exchange. When the company filed results on NSE today, or the
  SEBI deadline for a newer quarter has passed (45 days after the quarter, 60
  for the March year-end), the tool says so and points to the NSE filing. The
  filing is the source of truth: open it for the newest quarter.
- Standalone vs consolidated: Yahoo reports consolidated; NSE filings carry
  both.

## Steps

1. Run `facts.py TICKER`.
2. Say, in this order: the newest quarter's revenue and net income with their
   YoY change, the margin trend over the quarters shown, the TTM line, then any
   "Yahoo lags" line exactly as printed and the NSE filing links.
3. If the user pastes a results PDF's text or an earnings-call transcript,
   read it and sum up what changed (growth, margins, guidance, one-offs) with
   the numbers quoted from the text.
4. Results days move prices hard both ways; a good quarter is not a buy
   signal. Then `/trader-news-india` or `/trader-entry-india` if the user
   wants to go on.

## Rules

- Every number comes from the run or from text the user gave. Never estimate a
  missing quarter.
- Amounts in ₹ crore. Reported figures, not a forecast. Not advice.
