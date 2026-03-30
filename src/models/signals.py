"""
Generic trading signal model. indicator_a > indicator_b = bullish.
"""
from dataclasses import dataclass


@dataclass
class SignalData:
    symbol: str
    indicator_a: float       # primary indicator  (e.g. MACD line, short SMA)
    indicator_b: float       # secondary indicator (e.g. signal line, long SMA)
    current_price: float
    high_price: float
    low_price: float
    signal_strength: float   # ranking metric (higher = stronger bullish momentum)
    average_volume: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.indicator_a > self.indicator_b

    @property
    def is_bearish(self) -> bool:
        return self.indicator_a < self.indicator_b
