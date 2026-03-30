"""
param_sweep.py — Monte Carlo parameter sweep over (SHORT_SMA, LONG_SMA, N_STOCKS).

Data is loaded once. Signals are pre-computed once per SMA pair. All combos
share the same sampled start dates for a fair comparison. Results are written
incrementally to CSV (safe to interrupt).

Usage:  python param_sweep.py
"""

import csv
import os
import random
from datetime import date, datetime, timedelta
from itertools import product
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.backtest import Backtester, BacktestConfig, compute_metrics
from src.backtest.data import (
    load_all_symbols, build_arrays, get_all_trading_dates,
)
from src.backtest.signals import compute_sma_signals, precompute_signals


# +==============================================================+
# |                        SETTINGS                             |
# +==============================================================╝

SHORT_SMA_VALUES = list(range(50, 81, 10))
LONG_SMA_VALUES  = list(range(100, 151, 10))
N_STOCKS_VALUES  = [15, 25]
MIN_SMA_GAP      = 20

N_RUNS           = 1000
RUN_TRADING_DAYS = 252

INITIAL_CASH     = 100_000.0
OUTPUT_DIR       = "sweep_results"

# +==============================================================╝

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


_INSTRUMENT_CSV = os.path.join(
    os.path.dirname(__file__), '..', 'groww-bot', 'instrument.csv'
)

def get_nse_symbols() -> list:
    path = os.path.abspath(_INSTRUMENT_CSV)
    if not os.path.exists(path):
        print(f"Warning: instrument.csv not found at {path}")
        return []
    df  = pd.read_csv(path, dtype=str)
    eq  = df[
        (df['exchange']      == 'NSE') &
        (df['segment']       == 'CASH') &
        (df['series']        == 'EQ') &
        (df['buy_allowed']   == '1') &
        (df['sell_allowed']  == '1')
    ]
    symbols = [s + '.NS' for s in eq['trading_symbol'].dropna().unique()]
    print(f"Loaded {len(symbols)} NSE EQ symbols from instrument.csv")
    return symbols


def build_combo_grid(
    short_vals: List[int],
    long_vals: List[int],
    min_gap: int,
) -> List[Tuple[int, int]]:
    return [
        (s, l) for s, l in product(short_vals, long_vals)
        if l - s >= min_gap
    ]


def sample_start_dates(
    all_trading_dates: List[date],
    n_runs: int,
    warmup: int,
    end_d: date,
    run_trading_days: Optional[int] = None,
    min_run_days: int = 30,
) -> List[date]:
    required = run_trading_days if run_trading_days is not None else min_run_days
    td_ords  = np.array([d.toordinal() for d in all_trading_dates], dtype=np.int64)
    end_idx  = int(np.searchsorted(td_ords, end_d.toordinal(), side='right'))

    pool = [
        d for i, d in enumerate(all_trading_dates)
        if i >= warmup and (end_idx - (i + 1)) >= required
    ]
    k = min(n_runs, len(pool))
    if k < n_runs:
        print(f"  Note: only {len(pool)} valid start dates available; using {k} runs.")
    return random.sample(pool, k)


def run_single(
    signals_cache: Dict[int, list],
    arrays: Dict[str, tuple],
    window: List[date],
    start_d: date,
    end_d: date,
    cfg: BacktestConfig,
) -> Optional[dict]:
    bt = Backtester(arrays, cfg)
    for d in window:
        bt.step(d, signals_cache.get(d.toordinal(), []))
    return compute_metrics(bt, start_d, end_d, cfg.initial_cash) or None


def aggregate_combo(
    run_results: List[dict],
    short_sma: int,
    long_sma: int,
    n_stocks: int,
) -> dict:
    def _finite(key):
        return np.array(
            [r[key] for r in run_results if np.isfinite(r.get(key, float('nan')))],
            dtype=float,
        )

    xirr = _finite('xirr_pct')
    ret  = _finite('total_return')
    dd   = _finite('max_drawdown')
    sh   = _finite('sharpe')
    n    = len(run_results)
    profitable = sum(1 for r in run_results if r.get('total_return', 0) > 0)

    def _s(arr, key):
        if len(arr) == 0:
            return float('nan')
        return {
            'median': float(np.median(arr)),
            'mean':   float(arr.mean()),
            'std':    float(arr.std()),
            'p25':    float(np.percentile(arr, 25)),
            'p75':    float(np.percentile(arr, 75)),
        }[key]

    return {
        'short_sma':        short_sma,
        'long_sma':         long_sma,
        'n_stocks':         n_stocks,
        'n_runs':           n,
        'median_xirr':      _s(xirr, 'median'),
        'mean_xirr':        _s(xirr, 'mean'),
        'std_xirr':         _s(xirr, 'std'),
        'p25_xirr':         _s(xirr, 'p25'),
        'p75_xirr':         _s(xirr, 'p75'),
        'median_return':    _s(ret,  'median'),
        'mean_return':      _s(ret,  'mean'),
        'median_drawdown':  _s(dd,   'median'),
        'mean_drawdown':    _s(dd,   'mean'),
        'mean_sharpe':      float(sh.mean()) if len(sh) else float('nan'),
        'pct_profitable':   profitable / n * 100 if n else float('nan'),
    }


def print_sweep_table(combo_results: List[dict]):
    sorted_r = sorted(
        combo_results,
        key=lambda r: r.get('median_xirr', float('-inf')),
        reverse=True,
    )
    hdr = (
        f"{'#':>4}  {'Short':>5}  {'Long':>5}  {'N':>3}  {'Runs':>5}  "
        f"{'MedXIRR%':>9}  {'MeanXIRR%':>10}  {'Std%':>6}  "
        f"{'P25%':>6}  {'P75%':>6}  {'Profitable%':>12}"
    )
    print(f"\nPARAMETER SWEEP RESULTS  (sorted by median XIRR%)")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(sorted_r, 1):
        print(
            f"{i:>4}  {r['short_sma']:>5}  {r['long_sma']:>5}  {r['n_stocks']:>3}  "
            f"{r['n_runs']:>5}  "
            f"{r['median_xirr']:>8.1f}%  {r['mean_xirr']:>9.1f}%  "
            f"{r['std_xirr']:>5.1f}%  "
            f"{r['p25_xirr']:>5.1f}%  {r['p75_xirr']:>5.1f}%  "
            f"{r['pct_profitable']:>11.1f}%"
        )
    print("-" * len(hdr))
    if sorted_r:
        best = sorted_r[0]
        print(f"\nBest combo:  short={best['short_sma']}  long={best['long_sma']}  "
              f"n={best['n_stocks']}  ->  median XIRR {best['median_xirr']:.1f}%")


def save_sweep_heatmaps(combo_results: List[dict], path: str):
    if not MATPLOTLIB_AVAILABLE:
        print("Skipping heatmaps (matplotlib not installed).")
        return

    short_vals = sorted(SHORT_SMA_VALUES)
    long_vals  = sorted(LONG_SMA_VALUES)

    all_xirr = [r['median_xirr'] for r in combo_results
                if np.isfinite(r.get('median_xirr', float('nan')))]
    vmin = 0
    vmax = max(all_xirr) if all_xirr else 50

    cmap = plt.cm.RdYlGn.copy()
    cmap.set_bad(color='lightgrey')

    n_panels = len(N_STOCKS_VALUES)
    ncols    = min(n_panels, 3)
    nrows    = (n_panels + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(8 * ncols, 6 * nrows), squeeze=False)
    fig.suptitle(
        f"Parameter Sweep — Median XIRR% by SMA pair\n"
        f"({N_RUNS} Monte Carlo runs per combo)",
        fontsize=13, fontweight='bold',
    )

    for idx, n_stocks in enumerate(N_STOCKS_VALUES):
        ax = axes[idx // ncols][idx % ncols]

        grid = np.full((len(long_vals), len(short_vals)), float('nan'))
        for r in combo_results:
            if r['n_stocks'] != n_stocks:
                continue
            if r['short_sma'] not in short_vals or r['long_sma'] not in long_vals:
                continue
            ci = short_vals.index(r['short_sma'])
            ri = long_vals.index(r['long_sma'])
            grid[ri, ci] = r['median_xirr']

        im = ax.imshow(
            np.ma.masked_invalid(grid),
            cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax,
        )
        fig.colorbar(im, ax=ax, label='Median XIRR%', shrink=0.85)
        ax.set_xticks(range(len(short_vals)))
        ax.set_xticklabels(short_vals)
        ax.set_yticks(range(len(long_vals)))
        ax.set_yticklabels(long_vals)
        ax.set_xlabel('Short SMA')
        ax.set_ylabel('Long SMA')
        ax.set_title(f'N_STOCKS = {n_stocks}')

        for ri in range(len(long_vals)):
            for ci in range(len(short_vals)):
                val = grid[ri, ci]
                if np.isfinite(val):
                    ax.text(ci, ri, f"{val:.1f}%",
                            ha='center', va='center', fontsize=8, color='black')

    # Hide unused subplots
    for idx in range(n_panels, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Heatmap          -> {path}")


CSV_FIELDS = [
    'short_sma', 'long_sma', 'n_stocks', 'n_runs',
    'median_xirr', 'mean_xirr', 'std_xirr', 'p25_xirr', 'p75_xirr',
    'median_return', 'mean_return',
    'median_drawdown', 'mean_drawdown',
    'mean_sharpe', 'pct_profitable',
]


def main():
    end_d       = date.today()
    max_long    = max(LONG_SMA_VALUES)
    fetch_start = end_d - timedelta(days=365 * 20 + max_long + 30)
    total_days  = (end_d - fetch_start).days
    sma_pairs   = build_combo_grid(SHORT_SMA_VALUES, LONG_SMA_VALUES, MIN_SMA_GAP)
    n_combos    = len(sma_pairs) * len(N_STOCKS_VALUES)

    print(f"\n{'=' * 65}")
    print("  PARAMETER SWEEP")
    print(f"{'=' * 65}")
    print(f"  Short SMAs:    {SHORT_SMA_VALUES}")
    print(f"  Long SMAs:     {LONG_SMA_VALUES}")
    print(f"  N_STOCKS:      {N_STOCKS_VALUES}")
    print(f"  Min SMA gap:   {MIN_SMA_GAP}")
    print(f"  SMA pairs:     {len(sma_pairs)}   Total combos: {n_combos}")
    print(f"  Runs/combo:    {N_RUNS}   Run duration: {RUN_TRADING_DAYS or 'full range'} trading days")
    print(f"  Capital:       Rs.{INITIAL_CASH:,.0f}")
    print(f"{'=' * 65}\n")

    # Load symbols
    symbols = get_nse_symbols()
    if not symbols:
        print("No symbols found. Check groww-bot/instrument.csv exists.")
        return
    print(f"Symbol universe: {len(symbols)}\n")

    # Load data once for all symbols (up to 20 years)
    print(f"Loading data ({fetch_start} -> {end_d}) ...")
    base_config = BacktestConfig(
        initial_cash=INITIAL_CASH,
        long_period=max_long,
        short_period=SHORT_SMA_VALUES[0],
        n_symbols=N_STOCKS_VALUES[0],
        cache_dir="backtest_cache",
        mock_mode=False,
    )
    data = load_all_symbols(
        symbols, fetch_start, end_d, total_days,
        base_config, min_rows=max_long,
    )
    if not data:
        print("No data loaded.")
        return

    arrays    = build_arrays(data)
    all_dates = get_all_trading_dates(data)
    print(f"Symbols with sufficient data: {len(data)}")
    print(f"Total trading days available: {len(all_dates)}\n")

    # Sample start dates once — shared across all combos
    print(f"Sampling {N_RUNS} random start dates ...")
    start_dates = sample_start_dates(
        all_dates, N_RUNS,
        warmup=max_long,
        end_d=end_d,
        run_trading_days=RUN_TRADING_DAYS,
    )
    if not start_dates:
        print("No valid start dates found.")
        return
    print(f"  {len(start_dates)} start dates  "
          f"(range: {min(start_dates)} -> {max(start_dates)})\n")

    # Pre-build windows
    td_ords = np.array([d.toordinal() for d in all_dates], dtype=np.int64)
    end_ord = end_d.toordinal()
    end_idx = int(np.searchsorted(td_ords, end_ord, side='right'))

    windows: List[List[date]] = []
    valid_starts: List[date]  = []
    for s in sorted(start_dates):
        i_s = int(np.searchsorted(td_ords, s.toordinal(), side='left'))
        w   = (all_dates[i_s : min(i_s + RUN_TRADING_DAYS, end_idx)]
               if RUN_TRADING_DAYS else all_dates[i_s : end_idx])
        if len(w) >= 30:
            windows.append(w)
            valid_starts.append(s)
    print(f"  {len(windows)} valid windows after length check.\n")

    # Set up output directory + CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, "results.csv")
    with open(csv_path, 'w', newline='') as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore').writeheader()
    print(f"Results CSV      -> {csv_path}  (written incrementally)\n")

    # -- Sweep ----------------------------------------------------------------
    combo_results: List[dict] = []

    for pair_idx, (short, long_) in enumerate(sma_pairs, 1):
        print(f"[{pair_idx}/{len(sma_pairs)}]  short={short}  long={long_}")

        # Pre-compute signals for this SMA pair (reused across all N_STOCKS values)
        sig_config = BacktestConfig(
            initial_cash=INITIAL_CASH,
            long_period=long_,
            short_period=short,
            n_symbols=N_STOCKS_VALUES[0],
            cache_dir="backtest_cache",
            mock_mode=False,
        )
        signals_cache = precompute_signals(
            arrays, all_dates, sig_config, signals_fn=compute_sma_signals
        )

        for n_stocks in N_STOCKS_VALUES:
            run_cfg = BacktestConfig(
                initial_cash=INITIAL_CASH,
                long_period=long_,
                short_period=short,
                n_symbols=n_stocks,
                cache_dir="backtest_cache",
                mock_mode=False,
            )
            run_results: List[dict] = []
            for w, s_d in tqdm(
                zip(windows, valid_starts),
                total=len(windows),
                desc=f"  N={n_stocks:>2}",
                leave=False,
            ):
                r = run_single(signals_cache, arrays, w, s_d, w[-1], run_cfg)
                if r:
                    run_results.append(r)

            if run_results:
                combo = aggregate_combo(run_results, short, long_, n_stocks)
                combo_results.append(combo)
                # Write incrementally so results are safe even if interrupted
                with open(csv_path, 'a', newline='') as f:
                    csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore').writerow(combo)
                print(
                    f"    N={n_stocks:>2}: {len(run_results):>3} runs  "
                    f"median XIRR={combo['median_xirr']:>6.1f}%  "
                    f"profitable={combo['pct_profitable']:.0f}%"
                )

    print(f"\nSweep complete: {len(combo_results)} combos evaluated.")
    if not combo_results:
        print("No results — check your settings.")
        return

    print_sweep_table(combo_results)
    save_sweep_heatmaps(combo_results, path=os.path.join(OUTPUT_DIR, "heatmaps.png"))
    print(f"Sweep CSV        -> {csv_path}  ({len(combo_results)} rows)")


if __name__ == "__main__":
    main()
