#!/usr/bin/env python3
"""
Entry point for the Stratzy backtesting framework.

Usage:
    python main.py             # dry-run strategy with cached data
    python main.py --backtest  # full historical backtest
"""
import argparse
import os
import pandas as pd
from datetime import date, timedelta

from src.strategies.sma_crossover import SMAStrategy, SMAConfig
from src.backtest import (
    Backtester, BacktestConfig,
    compute_metrics, print_summary, save_trades_csv, save_equity_chart,
)
from src.backtest.data import (
    load_all_symbols, build_arrays,
    get_all_trading_dates, _try_load_cache,
)
from src.backtest.signals import compute_sma_signals, precompute_signals


# ============================================================
#                         SETTINGS
# ============================================================

LONG_SMA      = 150
SHORT_SMA     = 120
N_STOCKS      = 10
INITIAL_CASH  = 100_000
SIP_AMOUNT    = 20000

# ============================================================


_INSTRUMENT_CSV = os.path.join(
    os.path.dirname(__file__), '..', 'groww-bot', 'instrument.csv'
)


def get_nse_symbols() -> list:
    """Load all NSE EQ stocks from instrument.csv as yfinance tickers."""
    path = os.path.abspath(_INSTRUMENT_CSV)
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path, dtype=str)
    eq = df[
        (df['exchange'] == 'NSE') &
        (df['segment']  == 'CASH') &
        (df['series']   == 'EQ') &
        (df['buy_allowed'] == '1') &
        (df['sell_allowed'] == '1')
    ]
    symbols = [s + '.NS' for s in eq['trading_symbol'].dropna().unique()]
    print(f"Loaded {len(symbols)} NSE EQ symbols")
    return symbols


def get_symbols_from_cache(cache_dir: str) -> list:
    """Discover symbols from cached pickle files."""
    import glob
    files = glob.glob(os.path.join(cache_dir, "*.pkl"))
    return [os.path.basename(f).replace('.pkl', '') for f in files]


def make_backtest_config() -> BacktestConfig:
    """Build backtest configuration from the settings above."""
    return BacktestConfig(
        initial_cash=INITIAL_CASH,
        n_symbols=N_STOCKS,
        long_period=LONG_SMA,
        short_period=SHORT_SMA,
        sip_amount=SIP_AMOUNT,
        cache_dir="backtest_cache",
        mock_mode=False,
    )


def make_sma_config() -> SMAConfig:
    """Build strategy configuration from the settings above."""
    return SMAConfig(
        long_sma=LONG_SMA,
        short_sma=SHORT_SMA,
        n_symbols=N_STOCKS,
        initial_cash=INITIAL_CASH,
        data_lookback_days=LONG_SMA + 60,
    )


class CacheDataClient:
    """Data provider that reads from the local pickle cache."""

    def __init__(self, cache_dir: str = "backtest_cache"):
        self.cache_dir = cache_dir

    def get_all_symbols(self) -> list:
        syms = get_nse_symbols()
        return syms if syms else get_symbols_from_cache(self.cache_dir)

    def get_symbol_data(self, symbol: str, days: int):
        from src.models.symbol import SymbolData
        df = _try_load_cache(symbol, self.cache_dir)
        if df is None:
            return SymbolData(symbol, pd.DataFrame())
        return SymbolData(symbol, df.tail(days))


def run_backtest():
    """Execute a full historical backtest and save results."""
    config  = make_backtest_config()
    symbols = get_nse_symbols() or get_symbols_from_cache(config.cache_dir)

    if not symbols:
        print("No symbols found. Check that instrument.csv exists.")
        return

    print("\n" + "=" * 60)
    print("  SMA CROSSOVER BACKTEST")
    print("=" * 60)
    print(f"  Long SMA:     {LONG_SMA} days")
    print(f"  Short SMA:    {SHORT_SMA} days")
    print(f"  Stocks held:  {N_STOCKS}")
    print(f"  Capital:      Rs.{INITIAL_CASH:,.0f}")
    print(f"  Monthly SIP:  Rs.{SIP_AMOUNT:,.0f}" if SIP_AMOUNT else "  Monthly SIP:  None")
    print(f"  Universe:     {len(symbols)} NSE stocks")
    print("=" * 60)

    end_d       = date.today()
    fetch_start = end_d - timedelta(days=365 * 20 + LONG_SMA + 30)
    total_days  = (end_d - fetch_start).days

    print(f"\nFetching data from {fetch_start} -> {end_d} ...")

    data = load_all_symbols(
        symbols, fetch_start, end_d, total_days, config, min_rows=LONG_SMA,
    )
    if not data:
        print("No data loaded.")
        return

    all_dates    = get_all_trading_dates(data)
    actual_start = all_dates[0]
    years        = (end_d - actual_start).days // 365

    print(f"Loaded {len(data)} symbols  |  {actual_start} -> {end_d}  ({years} years)")

    arrays        = build_arrays(data)
    signals_cache = precompute_signals(arrays, all_dates, config, signals_fn=compute_sma_signals)

    bt = Backtester(arrays, config)
    bt.run(all_dates, signals_cache=signals_cache)

    m = compute_metrics(bt, actual_start, end_d, INITIAL_CASH)
    print_summary(m, config, str(actual_start), str(end_d), strategy_name="SMA Crossover")
    save_trades_csv(bt.trades, "backtest_trades.csv")
    save_equity_chart(bt.snapshots, config, str(actual_start), str(end_d),
                      strategy_name="SMA Crossover")


def run_strategy(dry_run: bool = True):
    """Run the SMA strategy in dry-run or live mode."""
    client   = CacheDataClient()
    strategy = SMAStrategy(make_sma_config(), client)
    strategy.run_strategy(dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Stratzy trading framework")
    parser.add_argument('--backtest', action='store_true')
    parser.add_argument('--live',     action='store_true')
    args = parser.parse_args()

    if args.backtest:
        run_backtest()
    else:
        run_strategy(dry_run=not args.live)


if __name__ == '__main__':
    main()
