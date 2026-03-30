"""
Symbol and historical data models
"""
from typing import Optional
import numpy as np


class SymbolData:
    """
    Historical OHLCV data for a symbol.

    Accepts data in two formats:
      1. Groww-style dict: {'candles': [[ts, o, h, l, c, v], ...]}
      2. pandas DataFrame with columns: date, open, high, low, close, volume
    """

    def __init__(self, symbol: str, data):
        self.symbol = symbol

        if isinstance(data, dict):
            self._from_candle_dict(data)
        else:
            self._from_dataframe(data)

    def _from_candle_dict(self, data: dict):
        import pytz
        from datetime import datetime
        candles = data.get('candles', [])
        if candles:
            arr = np.array(candles)
            tz = pytz.timezone("Asia/Kolkata")
            self.start_date = datetime.fromtimestamp(arr[0][0], tz=tz)
            self.end_date   = datetime.fromtimestamp(arr[-1][0], tz=tz)
            self.opens   = arr[:, 1].astype(float)
            self.highs   = arr[:, 2].astype(float)
            self.lows    = arr[:, 3].astype(float)
            self.closes  = arr[:, 4].astype(float)
            self.volumes = arr[:, 5].astype(float)
        else:
            self._empty()

    def _from_dataframe(self, df):
        if df is None or len(df) == 0:
            self._empty()
            return
        df = df.sort_values('date').reset_index(drop=True)
        self.start_date = df['date'].iloc[0]
        self.end_date   = df['date'].iloc[-1]
        self.opens   = df['open'].values.astype(float)
        self.highs   = df['high'].values.astype(float)
        self.lows    = df['low'].values.astype(float)
        self.closes  = df['close'].values.astype(float)
        self.volumes = df['volume'].values.astype(float)

    def _empty(self):
        self.start_date = None
        self.end_date   = None
        self.opens   = np.array([])
        self.highs   = np.array([])
        self.lows    = np.array([])
        self.closes  = np.array([])
        self.volumes = np.array([])

    def get_latest_sma(self, period: int) -> Optional[float]:
        if len(self.closes) < period:
            return None
        return float(np.mean(self.closes[-period:]))

    def get_average_volume(self, days: int = 30) -> float:
        if len(self.volumes) == 0:
            return 0.0
        return float(np.mean(self.volumes[-days:]))
