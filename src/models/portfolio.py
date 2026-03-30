"""
Portfolio and position models
"""
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional


@dataclass
class Position:
    """Represents a single holding in the portfolio"""
    symbol: str
    quantity: int
    avg_price: float
    purchase_date: str

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealised_pnl(self, current_price: float) -> float:
        return self.market_value(current_price) - (self.quantity * self.avg_price)

    def unrealised_pnl_pct(self, current_price: float) -> float:
        cost = self.quantity * self.avg_price
        return (self.unrealised_pnl(current_price) / cost * 100) if cost > 0 else 0.0


@dataclass
class Portfolio:
    """Portfolio state — cash + open positions"""
    cash: float
    positions: Dict[str, Position]

    def total_value(self, symbol_prices: Dict[str, float]) -> float:
        positions_value = sum(
            pos.market_value(symbol_prices.get(pos.symbol, pos.avg_price))
            for pos in self.positions.values()
        )
        return self.cash + positions_value

    def save(self, filepath: str = "portfolio.json"):
        data = {
            "cash": self.cash,
            "positions": {sym: asdict(pos) for sym, pos in self.positions.items()},
            "last_updated": datetime.now().isoformat(),
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Portfolio saved to {filepath}")

    @classmethod
    def load(cls, filepath: str = "portfolio.json") -> Optional['Portfolio']:
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r') as f:
            data = json.load(f)
        positions = {
            sym: Position(**pos_data)
            for sym, pos_data in data["positions"].items()
        }
        return cls(cash=data["cash"], positions=positions)
