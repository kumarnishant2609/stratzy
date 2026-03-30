# Frequently Asked Questions

## Strategy

**Q: What is the SMA crossover strategy?**
A: It compares two moving averages of a stock's closing price — a short-period SMA and a long-period SMA. When the short SMA crosses above the long SMA, the stock is gaining upward momentum (buy signal). When it crosses below, momentum is fading (sell signal).

**Q: How are stocks ranked?**
A: By signal strength = (Short SMA - Long SMA) / Price. Dividing by price ensures a Rs.500 stock and a Rs.5,000 stock are ranked fairly — raw difference alone would bias toward expensive stocks.

**Q: How many stocks are held at once?**
A: Configurable via N_STOCKS. The current setting is 10. Cash is split equally among all held positions.

**Q: When does the strategy sell a stock?**
A: Only when the short SMA drops below the long SMA for that stock. There is no fixed stop-loss or profit target.

**Q: Why SMA and not EMA?**
A: SMA is simpler and less sensitive to single-day price spikes. EMA reacts faster but generates more false signals in choppy markets. Both are available in the codebase if you want to experiment.

---

## Backtesting

**Q: What does the backtester actually do?**
A: It replays every trading day from the start date to the end date. Each day it checks all held positions for sell signals, then buys the top-ranked bullish stocks to fill empty portfolio slots. It records every trade and daily portfolio value.

**Q: How far back does the data go?**
A: Up to 20 years. The earliest data in the cache starts from September 2005. Data is downloaded via Yahoo Finance.

**Q: Why does the first trade happen months after the data starts?**
A: The long SMA (e.g. 150 days) needs 150 days of price history before it can be calculated. This warmup period has no trades — only data accumulation.

**Q: What price is used for buying and selling?**
A: Buys execute at (close + high) / 2 of the signal day. Sells execute at (close + low) / 2. This is a conservative estimate — worse than close but better than worst-case. It avoids the unrealistic assumption that you always trade at the exact closing price.

**Q: Is slippage modelled?**
A: Yes, through the execution price model above. The slippage percentage in the cost model is set to 0 because the high/low pricing already accounts for execution uncertainty. Adding both would be double-counting.

---

## Transaction Costs

**Q: What fees are included?**
A: STT (0.1% on buy and sell), NSE exchange charge (0.00322%), SEBI turnover fee (0.0001%), stamp duty (0.015% on buys only), GST (18% on brokerage + exchange + SEBI fees), and DP charge (Rs.15.93 flat per stock sold). These match real NSE delivery trading costs.

**Q: Is brokerage included?**
A: Brokerage is set to Rs.0. Most discount brokers (Zerodha, Groww) charge zero brokerage on delivery trades.

**Q: How much do costs eat into returns?**
A: Roughly 0.3-0.5% per round trip (buy + sell). Over hundreds of trades this is significant — the backtest accounts for every rupee.

---

## Volume Filter

**Q: What is the volume filter?**
A: If your estimated order size exceeds 10% of that day's traded volume for a stock, the stock is skipped. This prevents buying illiquid stocks where your order would move the market price against you.

**Q: Why 10% and not 5%?**
A: 5% is very conservative for delivery trades on NSE. 10% allows more candidates while still filtering out genuinely illiquid penny stocks.

---

## Parameter Sweep

**Q: What is a parameter sweep?**
A: It tests every combination of short SMA, long SMA, and portfolio size. For each combination, it runs 1,000 Monte Carlo simulations (random 1-year windows) and reports the median XIRR. This shows which parameters work consistently, not just in one cherry-picked period.

**Q: What are Monte Carlo simulations in this context?**
A: Instead of testing one fixed period (e.g. 2020-2021), we randomly pick 1,000 different start dates from the full 20-year history and run a 1-year backtest from each. The median result tells you what a "typical" year looks like for that parameter combo.

**Q: How do I read the heatmap?**
A: Darker green = higher median XIRR. Each cell shows one SMA combination. There are separate panels for different portfolio sizes (N_STOCKS). Look for clusters of dark green — those are the robust parameter regions.

**Q: What should I look for in the results?**
A: Not just high median_xirr but also low std_xirr (consistency) and high pct_profitable (reliability). A combo with 30% median XIRR and 40% std is less useful than one with 25% median XIRR and 15% std.

**Q: Why do neighboring parameter combos sometimes have very different results?**
A: If small changes in SMA lengths cause large swings in performance, the strategy is fragile in that region. The best combos are those where nearby cells also show good results — that means the strategy is robust to small parameter changes.

---

## SIP

**Q: Does the backtest support SIP?**
A: Yes. Set SIP_AMOUNT > 0 in main.py. Cash is added on the first trading day of each month.

**Q: Does the parameter sweep support SIP?**
A: No. The sweep always uses a lump sum investment to keep comparisons fair across combos.

---

## Performance Metrics

**Q: What is XIRR?**
A: Annualised return. If you invested Rs.1,00,000 and it became Rs.1,50,000 in 2 years, XIRR = (1.5)^(1/2) - 1 = 22.5% per year. It is directly comparable to FD rates or mutual fund CAGR.

**Q: What is max drawdown?**
A: The worst peak-to-trough decline. If your portfolio went from Rs.2,00,000 to Rs.1,40,000 before recovering, drawdown = (200000 - 140000) / 200000 = 30%. Lower is better.

**Q: What is the Sharpe ratio?**
A: Return per unit of risk. Calculated as mean daily return / std of daily returns, annualised by multiplying by sqrt(252). Above 1.0 is good. Above 2.0 is excellent. Below 0.5 means you are not being compensated enough for the volatility.

**Q: What is win rate?**
A: Percentage of completed round-trip trades (buy then sell of the same stock) that were profitable after fees. A 40% win rate can still be profitable if winning trades are much larger than losing trades.

**Q: Why is the win rate only ~38%?**
A: Momentum strategies typically have low win rates but high reward-to-risk ratios. Most small losses come from whipsaw trades in sideways markets. The few big winners during trending markets more than compensate.

---

## Data

**Q: Where does the price data come from?**
A: Yahoo Finance via the yfinance Python library. Daily OHLCV (Open, High, Low, Close, Volume) data.

**Q: What is the backtest_cache folder?**
A: Downloaded data is saved as pickle files (one per stock) so subsequent runs load instantly without re-downloading. Delete the folder to force a fresh download.

**Q: What is instrument.csv?**
A: A list of all NSE stocks with their trading symbols, segments, and permissions. It comes from the Groww broker API and is used to define the stock universe.

**Q: Is survivorship bias an issue?**
A: Partially. The stock universe is the current NSE listing. Stocks that were delisted or went bankrupt during the historical period may be underrepresented, which could inflate historical returns.

---

## Caveats

**Q: Can I use this for real trading?**
A: The dry-run mode prints what it would buy/sell but does not place real orders. There is no broker integration for live execution. This is a research and backtesting tool.

**Q: Are the returns realistic?**
A: The backtest includes all major transaction costs, conservative execution prices, and a volume filter. However, it does not model market impact (large orders moving the price) or survivorship bias. Actual live returns would likely be lower.

**Q: Does past performance guarantee future results?**
A: No. The parameters were optimised on historical data. Market conditions change. The strategy may underperform in future regimes that differ from the historical period.
