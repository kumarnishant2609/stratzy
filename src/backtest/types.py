from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    entry_date: str

    def market_value(self, price: float) -> float:
        return self.quantity * price


@dataclass
class Trade:
    date: str
    symbol: str
    action: str            # BUY | SELL
    qty: int
    price: float           # market price (pre-slippage)
    execution_price: float # actual execution price (post-slippage)
    cost: float            # total fees
    portfolio_value: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DailySnapshot:
    date: str
    cash: float
    positions_value: float
    total_value: float
