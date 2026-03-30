"""Technical indicator calculations."""
import numpy as np
from numpy import ndarray
from typing import Tuple


def moving_average(a, n: int = 3) -> ndarray:
    """Simple moving average via cumulative sum. Returns array of length len(a) - n + 1."""
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n


def ema(prices: ndarray, period: int) -> ndarray:
    """Exponential moving average. First (period-1) values are NaN."""
    prices = np.asarray(prices, dtype=float)
    if len(prices) < period:
        return np.full(len(prices), np.nan)

    result = np.full(len(prices), np.nan)
    multiplier = 2.0 / (period + 1)
    result[period - 1] = np.mean(prices[:period])

    for i in range(period, len(prices)):
        result[i] = prices[i] * multiplier + result[i - 1] * (1 - multiplier)

    return result


def rsi(closes: ndarray, period: int = 14) -> ndarray:
    """Relative Strength Index (0-100). First `period` values are NaN."""
    closes = np.asarray(closes, dtype=float)
    result = np.full(len(closes), np.nan)

    if len(closes) < period + 1:
        return result

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(closes)):
        if i == period:
            ag, al = avg_gain, avg_loss
        else:
            ag = (avg_gain * (period - 1) + gains[i - 1]) / period
            al = (avg_loss * (period - 1) + losses[i - 1]) / period
            avg_gain, avg_loss = ag, al

        rs = ag / al if al != 0 else float('inf')
        result[i] = 100 - (100 / (1 + rs))

    return result


def bollinger_bands(closes: ndarray, period: int = 20,
                    n_std: float = 2.0) -> Tuple[ndarray, ndarray, ndarray]:
    """Bollinger Bands. Returns (upper, middle, lower)."""
    closes = np.asarray(closes, dtype=float)
    middle = np.full(len(closes), np.nan)
    upper  = np.full(len(closes), np.nan)
    lower  = np.full(len(closes), np.nan)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        m = np.mean(window)
        s = np.std(window, ddof=0)
        middle[i] = m
        upper[i]  = m + n_std * s
        lower[i]  = m - n_std * s

    return upper, middle, lower
