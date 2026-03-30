from dataclasses import dataclass, field
from .costs import TransactionCosts


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    n_symbols: int = 10
    costs: TransactionCosts = field(default_factory=TransactionCosts)
    max_daily_move: float = 1.0    # reject price spike > 100% vs prior close
    cache_dir: str = "backtest_cache"
    mock_mode: bool = True         # True = only use cached data, never fetch

    # SIP — set sip_amount > 0 to add cash every month
    sip_amount: float = 0.0        # Rs. added on the first trading day of each month

    # Volume filter — skip stocks where order size > X% of avg daily volume
    volume_filter_pct: float = 0.10  # 10% of avg daily volume

    # SMA parameters
    long_period: int = 150
    short_period: int = 120
