"""
Abstract base class for all trading strategies
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from ..models.signals import SignalData
from ..models.portfolio import Portfolio


class BaseStrategy(ABC):
    """
    All strategies must inherit from this and implement the three abstract methods.

    The `data_client` is any object that provides:
        get_symbol_data(symbol, days) -> SymbolData
        get_all_symbols() -> List[str]
    """

    def __init__(self, data_client):
        self.data_client = data_client
        self.portfolio: Optional[Portfolio] = None

    @abstractmethod
    def calculate_signals(self, symbols: List[str]) -> List[SignalData]:
        """Compute and rank trading signals for the given symbol universe."""
        pass

    @abstractmethod
    def rebalance_portfolio(self, signals: List[SignalData], dry_run: bool = True):
        """Execute exits and entries based on signals."""
        pass

    @abstractmethod
    def run_strategy(self, dry_run: bool = True):
        """Full strategy execution: load portfolio -> signals -> rebalance -> save."""
        pass
