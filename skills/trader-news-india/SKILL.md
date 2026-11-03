---
name: trader-news-india
description: 'News Monitor, India (NSE) edition. Reads NSE''s official filings feeds (today''s company announcements, results filings, board meetings and corporate actions), matches them to your .NS tickers, tags each item (results, deal, legal, management, capital, rating, exchange query, analyst meet, dividend...) and shows only what is new since the last check, newest first, in IST, with each stock''s move from yesterday''s close. Also whole-market views: every results filing today, upcoming board meetings, dividends. Use: "any news on ANGELONE", "why is this moving", "news on my watchlist", "who reported results today", "morning briefing" for NSE stocks.'
---

# trader-news-india

What moved a stock, from the source: NSE's own filings. Results, board
outcomes, orders won, deals, management changes, regulatory actions, NSE's
"spurt in volume" queries, earnings-call schedules, dividends.

```bash
python3 ~/.claude/skills/trader-news-india/news.py                       # watchlist + plan + portfolio
python3 ~/.claude/skills/trader-news-india/news.py --tickers ANGELONE.NS MARICO.NS
python3 ~/.claude/skills/trader-news-india/news.py --tickers TCS.NS --all # everything today, seen or not, routine too
python3 ~/.claude/skills/trader-news-india/news.py --market results       # every results filing today, whole market
python3 ~/.claude/skills/trader-news-india/news.py --market important     # results, deals, legal... whole market
python3 ~/.claude/skills/trader-news-india/news.py --market board_meetings # upcoming results dates
python3 ~/.claude/skills/trader-news-india/news.py --market dividends
```

Flags: `--no-moves`, `--json`, `--state FILE`, `--offline DIR`.

## Sources

| feed (nsearchives.nseindia.com/content/RSS/) | what |
| --- | --- |
| `Online_announcements.xml` | every company announcement filed **today** (since midnight IST) |
| `Financial_Results.xml` | the latest results filings |
| `Board_Meetings.xml` | upcoming board meetings and what they will consider |
| `Corporate_action.xml` | dividends, splits, bonus issues with ex-dates |

The feeds name the company, not the ticker. Names are matched to tickers
with NSE's equity list (`trader/universe.txt` from trader-scanner-india, or
`EQUITY_L.csv`). The move line is Yahoo's chart endpoint (free, delayed).

**Limits, say them when they matter:**
- The announcements feed only holds today. Run it at least once a day (evening
  after filings, and before 9:15) so nothing slips past; the state file
  remembers what was seen for 30 days.
- No media headlines: Economic Times, Moneycontrol and Google News are not
  reachable from this environment's network. A filing is the primary source;
  analyst rating changes and rumours are not in it.
- NSE's JSON API (nseindia.com/api) is bot-protected and is not used.

## Steps

1. Run it on the watchlist (or the tickers the user names).
2. Report the moves first, then the `!` items (results, deal, legal,
   management, capital, rating, exchange query), each with its link.
3. A big move with no filing today: say so plainly. The cause may be a filing
   from yesterday, sector news or the market, which this tool does not see.
4. For results, hand on to `/trader-analyst-india TICKER` for the numbers.
5. Then `/trader-entry-india` if the user still wants to trade it. Never pick
   for them.

## Rules

- A filing is what the company said, not what the price will do. Not advice.
- Always give the link so the user can open the filing.
- Times are IST.
