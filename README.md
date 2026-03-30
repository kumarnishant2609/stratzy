# Stratzy — SMA Crossover Momentum Strategy & Backtesting Framework

A systematic, rule-based equity trading strategy framework for the Indian stock market (NSE), with a full backtesting engine, Monte Carlo simulation, and parameter optimization.

## What Does It Do?

- Scans the **entire NSE equity universe** (~2000 stocks) daily
- Identifies stocks with upward momentum using **SMA (Simple Moving Average) crossover**
- Ranks them by signal strength and holds the top N in a portfolio
- Exits positions when momentum reverses
- Includes a **backtesting engine** that replays 20 years of historical data day-by-day
- Runs **Monte Carlo simulations** across thousands of random start dates
- Performs **parameter sweeps** to find the most robust SMA/portfolio combinations

## Strategy Logic

```
Buy Signal:   Short SMA > Long SMA  (stock trending up)
Sell Signal:  Short SMA < Long SMA  (momentum reversing)
Ranking:      (Short SMA - Long SMA) / Price  (normalised momentum strength)
```

- Buys the top-ranked bullish stocks up to a portfolio limit
- Equal cash allocation across all positions
- Buy execution price: `(close + high) / 2` — conservative estimate
- Sell execution price: `(close + low) / 2` — conservative estimate
- Volume filter removes illiquid stocks (order > 10% of daily volume)
- All trades account for realistic NSE costs (STT, exchange fees, SEBI, GST, stamp duty, DP charges)

## Project Structure

```
stratzy/
├── main.py                  # Entry point: dry-run strategy or single backtest
├── param_sweep.py           # Parameter sweep with Monte Carlo simulations
├── requirements.txt
├── .gitignore
│
└── src/
    ├── backtest/            # Backtesting engine
    │   ├── config.py        # All configurable parameters
    │   ├── costs.py         # NSE transaction cost model
    │   ├── data.py          # Data loading (pickle cache / yfinance)
    │   ├── engine.py        # Day-by-day portfolio simulator
    │   ├── metrics.py       # XIRR, Sharpe, max drawdown, win rate
    │   ├── output.py        # Terminal output, CSV export, equity charts
    │   ├── signals.py       # SMA signal computation
    │   └── types.py         # Position, Trade, DailySnapshot dataclasses
    │
    ├── models/              # Data models
    │   ├── portfolio.py     # Portfolio & Position (for live/dry-run)
    │   ├── signals.py       # SignalData (generic indicator model)
    │   └── symbol.py        # SymbolData (OHLCV wrapper)
    │
    ├── strategies/          # Trading strategies
    │   ├── base.py          # Abstract base class
    │   └── sma_crossover.py # SMA crossover implementation
    │
    └── utils/               # Technical indicators
        └── indicators.py    # SMA, EMA, RSI, Bollinger Bands
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Data Setup

The strategy scans all NSE EQ stocks. It needs an `instrument.csv` file with the stock universe. Place it at `../groww-bot/instrument.csv` relative to the project root, or modify the `_INSTRUMENT_CSV` path in `main.py`.

The CSV must have columns: `exchange`, `segment`, `series`, `trading_symbol`, `buy_allowed`, `sell_allowed`.

Historical price data is downloaded automatically via **yfinance** on the first run and cached locally in `backtest_cache/`.

### 3. Run a Backtest

Edit the settings at the top of `main.py`:

```python
LONG_SMA      = 150
SHORT_SMA     = 120
N_STOCKS      = 10
INITIAL_CASH  = 100_000
SIP_AMOUNT    = 0         # set > 0 for monthly SIP
```

Then run:

```bash
python main.py --backtest
```

**Output:**
- Terminal summary (XIRR, Sharpe, drawdown, win rate)
- `backtest_trades.csv` — every buy/sell trade
- `backtest_equity.png` — portfolio value chart

### 4. Run a Parameter Sweep

Edit the settings at the top of `param_sweep.py`:

```python
SHORT_SMA_VALUES = list(range(80, 131, 10))
LONG_SMA_VALUES  = list(range(120, 201, 10))
N_STOCKS_VALUES  = [10, 15, 20]
N_RUNS           = 1000    # Monte Carlo runs per combo
```

Then run:

```bash
python param_sweep.py
```

**Output:**
- `sweep_results/results.csv` — every combo ranked by median XIRR
- `sweep_results/heatmaps.png` — colour-coded performance grid
- Terminal table sorted by best combo

## Transaction Cost Model

Every trade in the simulation deducts realistic Indian market costs:

| Fee | Rate |
|-----|------|
| STT | 0.1% (buy & sell) |
| NSE Exchange Charge | 0.00322% |
| SEBI Fee | 0.0001% |
| Stamp Duty | 0.015% (buy only) |
| GST | 18% on (brokerage + exchange + SEBI) |
| DP Charge | ₹15.93 flat per stock sold |

Execution price modelling:
- Buys execute at `(close + high) / 2` of the signal day
- Sells execute at `(close + low) / 2` of the signal day

## Performance Metrics

| Metric | Description |
|--------|-------------|
| **XIRR** | Annualised return (comparable to FD/mutual fund CAGR) |
| **Sharpe Ratio** | Return per unit of risk (>1 is good, >2 is excellent) |
| **Max Drawdown** | Worst peak-to-trough loss |
| **Win Rate** | % of round-trip trades that were profitable |

## Disclaimer

This is a personal research and backtesting tool. Past performance does not guarantee future results. Not financial advice. Use at your own risk.
