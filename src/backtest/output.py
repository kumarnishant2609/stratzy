import csv
from datetime import datetime
from typing import List

import numpy as np

from .types import Trade, DailySnapshot
from .config import BacktestConfig

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def print_summary(m: dict, config: BacktestConfig, start_date: str, end_date: str,
                  strategy_name: str = "Backtest"):
    print("\n" + "=" * 52)
    print(f"  {strategy_name.upper()} RESULTS")
    print("=" * 52)
    print(f"  Period:          {start_date} -> {end_date}")
    print(f"  Initial Capital: Rs.{config.initial_cash:>12,.2f}")
    print(f"  Final Value:     Rs.{m['final_value']:>12,.2f}")
    print(f"  Total Return:    {m['total_return']:>11.2f}%")
    print(f"  XIRR:            {m['xirr_pct']:>11.2f}%")
    print(f"  Max Drawdown:    {m['max_drawdown']:>11.2f}%")
    print(f"  Sharpe Ratio:    {m['sharpe']:>12.2f}")
    print(f"  Total Trades:    {m['total_trades']:>12}")
    print(f"  Win Rate:        {m['win_rate']:>11.2f}%")
    print("=" * 52)


def save_trades_csv(trades: List[Trade], path: str = "backtest_trades.csv"):
    if not trades:
        print("No trades to save.")
        return
    fields = ['date', 'symbol', 'action', 'qty', 'price',
              'execution_price', 'cost', 'portfolio_value']
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(t.to_dict() for t in trades)
    print(f"Trades CSV   -> {path}  ({len(trades)} rows)")


def save_equity_chart(snaps: List[DailySnapshot], config: BacktestConfig,
                      start_date: str, end_date: str,
                      strategy_name: str = "Strategy",
                      path: str = "backtest_equity.png"):
    if not MATPLOTLIB_AVAILABLE:
        print("Skipping equity chart (matplotlib not installed).")
        return
    if not snaps:
        return

    dates  = [datetime.strptime(s.date, "%Y-%m-%d") for s in snaps]
    values = [s.total_value for s in snaps]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(dates, values, lw=2, color='#2E86AB', label='Portfolio Value')
    ax.axhline(config.initial_cash, color='red', ls='--', alpha=0.5,
               label='Initial Capital')
    ax.fill_between(dates, config.initial_cash, values, alpha=0.08, color='#2E86AB')
    ax.set_title(
        f"Equity Curve — {strategy_name}  ({start_date} -> {end_date})",
        fontsize=13, fontweight='bold',
    )
    ax.set_xlabel('Date')
    ax.set_ylabel('Portfolio Value (Rs.)')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'Rs.{x:,.0f}'))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.xticks(rotation=45)
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Equity chart -> {path}")


def save_results_csv(results: List[dict], path: str = "backtest_runs.csv"):
    if not results:
        print("No results to save.")
        return
    fields = [
        'start_date', 'end_date', 'n_trading_days', 'final_value',
        'total_return', 'xirr_pct', 'max_drawdown', 'sharpe',
        'total_trades', 'win_rate',
    ]
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    print(f"Results CSV  -> {path}  ({len(results)} rows)")
