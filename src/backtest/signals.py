"""
Signal computation for backtesting.

Returns 8-element tuples per stock per day:
    (symbol, indicator_a, indicator_b, high, low, close, volume, strength)

indicator_a > indicator_b = bullish.
"""
from datetime import date
from typing import Dict, List

import numpy as np
from tqdm import tqdm

from .config import BacktestConfig


def compute_sma_signals(arrays: Dict[str, tuple], d_ord: int,
                        config: BacktestConfig) -> List[tuple]:
    """Compute SMA crossover signals for one trading day."""
    day_sigs = []
    for sym, (ords, closes, highs, lows, volumes) in arrays.items():
        idx = int(np.searchsorted(ords, d_ord, side='right')) - 1
        if idx < 0 or ords[idx] != d_ord:
            continue
        price = float(closes[idx])
        if price <= 0:
            continue
        if idx > 0:
            prev = float(closes[idx - 1])
            if prev > 0 and abs(price / prev - 1) > config.max_daily_move:
                continue
        idx_r = idx + 1
        if idx_r < config.long_period:
            continue
        short = float(closes[idx_r - config.short_period:idx_r].mean())
        long_ = float(closes[idx_r - config.long_period:idx_r].mean())
        strength = (short - long_) / price

        high    = float(highs[idx])
        low     = float(lows[idx])
        day_vol = float(volumes[idx])

        day_sigs.append((sym, short, long_, high, low, price, day_vol, strength))

    day_sigs.sort(key=lambda x: x[7], reverse=True)
    return day_sigs


def precompute_signals(arrays: Dict[str, tuple],
                       all_trading_dates: List[date],
                       config: BacktestConfig,
                       signals_fn=None) -> Dict[int, List[tuple]]:
    """Pre-compute signals for all trading dates. Defaults to SMA crossover."""
    if signals_fn is None:
        signals_fn = compute_sma_signals

    result: Dict[int, List[tuple]] = {}
    for d in tqdm(all_trading_dates, desc="Pre-computing signals"):
        result[d.toordinal()] = signals_fn(arrays, d.toordinal(), config)
    return result
