"""
Data loading for backtesting.

Supports pickle cache (mock_mode=True) and yfinance download (mock_mode=False).
"""
import os
import pickle
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

from .config import BacktestConfig


def _try_load_cache(symbol: str, cache_dir: str) -> Optional[pd.DataFrame]:
    path = os.path.join(cache_dir, f"{symbol}.pkl")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as f:
            raw = pickle.load(f)
        df = raw['df'] if isinstance(raw, dict) else raw
        if isinstance(df, pd.DataFrame) and len(df) > 0:
            return df
    except Exception:
        pass
    return None


def _save_cache(symbol: str, df: pd.DataFrame, cache_dir: str):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{symbol}.pkl")
    with open(path, 'wb') as f:
        pickle.dump({'df': df, 'cached_at': datetime.now()}, f)


def _fetch_yfinance(symbol: str, total_days: int,
                    cache_dir: str) -> Optional[pd.DataFrame]:
    """
    Download data via yfinance and save to cache.

    symbol should be a valid Yahoo Finance ticker (e.g. "RELIANCE.NS").
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError(
            "yfinance is not installed. Run: pip install yfinance\n"
            "Or set mock_mode=True and provide cached data."
        )

    try:
        end_dt = datetime.today()
        start_dt = end_dt - timedelta(days=total_days + 30)  # extra buffer

        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_dt.strftime('%Y-%m-%d'),
                              end=end_dt.strftime('%Y-%m-%d'),
                              interval='1d', auto_adjust=True)

        if hist is None or hist.empty:
            return None

        hist = hist.reset_index()
        hist.columns = [c.lower() for c in hist.columns]

        # Normalise date column
        if 'date' in hist.columns:
            hist['date'] = pd.to_datetime(hist['date']).dt.date
        elif 'datetime' in hist.columns:
            hist['date'] = pd.to_datetime(hist['datetime']).dt.date
            hist = hist.drop(columns=['datetime'])

        df = (hist[['date', 'open', 'high', 'low', 'close', 'volume']]
              .sort_values('date')
              .drop_duplicates('date')
              .reset_index(drop=True))

        _save_cache(symbol, df, cache_dir)
        return df
    except Exception:
        return None


def get_symbol_data(symbol: str, fetch_start: date, fetch_end: date,
                    total_days: int, config: BacktestConfig) -> Optional[pd.DataFrame]:
    """
    Return OHLCV DataFrame for [fetch_start, fetch_end].

    Loads from cache when available; fetches via yfinance when mock_mode=False
    and the cache doesn't cover the requested range.
    """
    df = _try_load_cache(symbol, config.cache_dir)

    if df is not None:
        df = df.copy()
        df['date'] = pd.to_datetime(df['date']).dt.date
        cache_min = df['date'].min()
        cache_max = df['date'].max()
        covers = (cache_min <= fetch_start) and (cache_max >= fetch_end)

        if config.mock_mode or covers:
            mask = (df['date'] >= fetch_start) & (df['date'] <= fetch_end)
            result = df[mask].reset_index(drop=True)
            return result if len(result) > 0 else None

    if config.mock_mode:
        return None

    # Live mode: fetch from yfinance
    df = _fetch_yfinance(symbol, total_days, config.cache_dir)
    if df is None:
        return None
    df['date'] = pd.to_datetime(df['date']).dt.date
    mask = (df['date'] >= fetch_start) & (df['date'] <= fetch_end)
    result = df[mask].reset_index(drop=True)
    return result if len(result) > 0 else None


def load_all_symbols(symbols: List[str], fetch_start: date, fetch_end: date,
                     total_days: int, config: BacktestConfig,
                     min_rows: int = 0) -> Dict[str, pd.DataFrame]:
    """Load data for all symbols. Filters out any with fewer than min_rows rows."""
    if min_rows == 0:
        min_rows = config.long_period
    data: Dict[str, pd.DataFrame] = {}
    for sym in tqdm(symbols, desc="Loading data"):
        df = get_symbol_data(sym, fetch_start, fetch_end, total_days, config)
        if df is not None and len(df) >= min_rows:
            data[sym] = df
    return data


def build_arrays(data: Dict[str, pd.DataFrame]) -> Dict[str, tuple]:
    """Convert DataFrames to (ordinals, closes, highs, lows, volumes) numpy arrays."""
    arrays = {}
    for sym, df in data.items():
        sdf = df.sort_values('date')
        ordinals = np.array([d.toordinal() for d in sdf['date']], dtype=np.int64)
        closes   = sdf['close'].values.astype(np.float64)
        highs    = sdf['high'].values.astype(np.float64)
        lows     = sdf['low'].values.astype(np.float64)
        volumes  = sdf['volume'].values.astype(np.float64)
        arrays[sym] = (ordinals, closes, highs, lows, volumes)
    return arrays


def price_at(arrays: dict, symbol: str, d_ord: int) -> Optional[float]:
    if symbol not in arrays:
        return None
    ords, closes, *_ = arrays[symbol]
    idx = np.searchsorted(ords, d_ord, side='right') - 1
    if idx < 0 or ords[idx] != d_ord:
        return None
    return float(closes[idx])


def sma_at(arrays: dict, symbol: str, d_ord: int, period: int) -> Optional[float]:
    if symbol not in arrays:
        return None
    ords, closes, *_ = arrays[symbol]
    idx = int(np.searchsorted(ords, d_ord, side='right'))
    if idx < period:
        return None
    return float(closes[idx - period:idx].mean())


def get_trading_dates(data: Dict[str, pd.DataFrame],
                      start_d: date, end_d: date) -> List[date]:
    all_dates: set = set()
    for df in data.values():
        mask = (df['date'] >= start_d) & (df['date'] <= end_d)
        all_dates.update(df.loc[mask, 'date'])
    return sorted(all_dates)


def get_all_trading_dates(data: Dict[str, pd.DataFrame]) -> List[date]:
    all_dates: set = set()
    for df in data.values():
        all_dates.update(df['date'])
    return sorted(all_dates)
