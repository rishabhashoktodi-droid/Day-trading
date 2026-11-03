# How to place an opening-range trade in Zerodha Kite (beginner, step by step)

Claude watches the charts and tells you **when**, **what**, **how many**, the **stop-loss** and the **target**.
You type the orders into the Kite app yourself. Claude never places anything.

> **Start with paper trading.** For the first 2–3 weeks, do every step below *except the final swipe*. Write the
> numbers down, and Claude logs the result as if you had traded. Real money only after that, and only if the
> results are good. Most beginners who day trade lose money.

---

## Words you'll see

| word | meaning |
| --- | --- |
| **Intraday (MIS)** | You buy and sell the same day. Kite closes it for you at about 3:25 PM if you don't (₹50 + GST charge). |
| **Market order** | Buy or sell right now, at whatever the price is. |
| **Limit order** | Buy or sell only at your price or better. It waits until the price gets there. |
| **SL-M (stop-loss market)** | A safety sell that waits. When the price falls to the **trigger**, it sells at market. This caps your loss. |
| **SL (stop-loss limit)** | Like SL-M, but it sells at your limit price or better. Use it only if Kite doesn't offer SL-M. |
| **Opening range** | The high and low of the first 15 minutes, 9:15–9:30 AM. |
| **Breakout / trigger** | A 5-minute candle *closes* above the opening-range high. That's the buy signal. |
| **R** | Your risk on one trade (about ₹100). A "1R target" means aiming to make about ₹100. |

---

## The evening before (or by 9:00 AM)
1. Install **Kite by Zerodha** on your phone and log in (password + PIN/TOTP). Check you can open it.
2. **Add money:** Profile (bottom right) → **Funds** → **Add funds** → UPI. ₹10,000 is the plan.
3. Add the day's stocks to a watchlist: tap the **search bar** in the Watchlist tab, type `CDSL`, tap **+** next
   to the **NSE** one. Repeat for the other shortlist stocks.

## 8:45 AM
4. Message Claude: **"morning news on my shortlist"**. Claude checks overnight company filings. A stock with
   surprise news may be dropped.

## 9:15–9:35 AM: do nothing
5. The market opens at 9:15. The first 15 minutes set the opening range. **Don't buy yet.** Opening prices jump
   around a lot.

## From 9:35 AM: wait for a signal
6. Message Claude: **"watch my shortlist"**. Claude checks every 5 minutes and replies **WAITING** (how far each
   stock is from its range high) or **TRIGGERED**.
7. When a stock triggers, Claude replies with a **ticket**, for example:
   ```
   BUY 6 CDSL, Intraday (MIS), Market
   Stop-loss: SL-M sell, trigger 1274.30
   Target:    Limit sell, price 1307.30
   Max loss about ₹99 + ₹8 charges
   ```
   Not every day triggers. A day with no signal is a normal day; just don't trade.

## Placing the trade (about 2 minutes, in this order)

**Step A: Buy**
1. Watchlist → tap **CDSL** → **BUY**.
2. Top of the order screen: choose **NSE**.
3. Product: **Intraday**. *Not* "Longterm/CNC".
4. Qty: **6** (exactly the ticket's number).
5. Order type: **Market**.
6. Check everything once, then **swipe to buy**. (Paper trading: stop here and just note the time and price.)
7. Bottom tabs → **Orders** → it should say **COMPLETE**. Note the price you got.

**Step B: Stop-loss, immediately after the buy**
1. Watchlist → **CDSL** → **SELL**.
2. **NSE**, **Intraday**, Qty **6**.
3. Order type: **SL-M**. Trigger price: **1274.30**.
   - If there's no SL-M, choose **SL**: trigger **1274.30**, price **1273.80** (the ticket gives both).
4. Swipe to sell. Orders tab: it shows **TRIGGER PENDING**. That's correct; it's waiting.

**Step C: Target**
1. Watchlist → **CDSL** → **SELL**.
2. **NSE**, **Intraday**, Qty **6**.
3. Order type: **Limit**. Price: **1307.30** (the target).
4. Swipe to sell. Orders tab: it shows **OPEN**.

You now have one buy done and two sells waiting: the stop below and the target above.

## While the trade is open
8. Message Claude: **"watch my trade"**. Claude alerts you if the stop or target is hit, and at 3:15 PM.
9. **Don't move the stop lower.** Ever. That's how small losses become big ones.
10. **The moment one sell fills, cancel the other.** Orders tab → tap the still-waiting order → **Cancel**.
    If you forget, the second order can fire later and sell shares you no longer own (an accidental short sale).
11. Check **Portfolio → Positions**: after the exit, CDSL should show quantity **0**.

## 3:15 PM: out, no matter what
12. If neither sell has filled by **3:15 PM**:
    - Orders tab → **cancel both** waiting sells.
    - Portfolio → Positions → tap **CDSL** → **Exit** (sell 6, Market).
    - Positions should show **0**.

## After the trade
13. Tell Claude the buy and sell prices ("bought 6 CDSL at 1291, sold at 1307.30"). Claude records it so the daily
    limits work: **max 2 trades a day** and **stop for the day after ₹200 lost**.

---

## If something goes wrong
- **Order REJECTED:** tap it to read why. Usually not enough funds, or a price off the tick (use Claude's prices exactly).
- **Bought but forgot the stop-loss:** place Step B right now.
- **Price gaps far below your stop:** SL-M sells at the next available price, so the loss can be bigger than ₹100.
  That's normal and rare.
- **Unsure about anything:** don't trade. Exit with Positions → Exit, and ask Claude.
