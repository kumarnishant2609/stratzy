from datetime import date
from typing import Callable, Dict, List, Optional

from tqdm import tqdm

from .config import BacktestConfig
from .costs import calc_buy_cost, calc_sell_cost
from .types import Position, Trade, DailySnapshot
from .data import price_at
from .signals import compute_sma_signals


class Backtester:
    """
    Event-driven backtester.

    Each day it receives a list of signal tuples:
        (symbol, indicator_a, indicator_b, high, low, close, volume, strength)

    Decision rule:
        - Exit:  sell held positions where indicator_a < indicator_b
        - Enter: buy top bullish signals not already held
    """

    def __init__(self, arrays: Dict[str, tuple], config: BacktestConfig):
        self.arrays = arrays
        self.config = config
        self.cash = config.initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.snapshots: List[DailySnapshot] = []

    def _pv(self, d_ord: int) -> float:
        pos_val = sum(
            pos.market_value(price_at(self.arrays, sym, d_ord) or pos.avg_price)
            for sym, pos in self.positions.items()
        )
        return self.cash + pos_val

    def _sell(self, symbol: str, d: date, price: float):
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return
        total_fees, _ = calc_sell_cost(price, pos.quantity, self.config.costs)
        self.cash += pos.quantity * price - total_fees
        self.trades.append(Trade(
            date=str(d), symbol=symbol, action="SELL",
            qty=pos.quantity, price=price, execution_price=price,
            cost=total_fees, portfolio_value=self._pv(d.toordinal()),
        ))

    def _buy(self, symbol: str, d: date, price: float, alloc: float):
        total_fees, _ = calc_buy_cost(price, 1, self.config.costs)
        cost_per_share = price + total_fees
        qty = int(alloc / cost_per_share)
        if qty <= 0:
            return
        total_fees, _ = calc_buy_cost(price, qty, self.config.costs)
        total = qty * price + total_fees
        if total > self.cash + 0.01:
            qty -= 1
            if qty <= 0:
                return
            total_fees, _ = calc_buy_cost(price, qty, self.config.costs)
            total = qty * price + total_fees
            if total > self.cash + 0.01:
                return
        self.cash -= total
        self.positions[symbol] = Position(
            symbol=symbol, quantity=qty, avg_price=price, entry_date=str(d)
        )
        self.trades.append(Trade(
            date=str(d), symbol=symbol, action="BUY",
            qty=qty, price=price, execution_price=price,
            cost=total_fees, portfolio_value=self._pv(d.toordinal()),
        ))

    def step(self, d: date, signals: List[tuple]):
        """
        Advance portfolio by one trading day.

        signals: list of (sym, ind_a, ind_b, high, low, close, avg_vol, strength)
                 tuples, sorted by strength descending.
        """
        d_ord = d.toordinal()
        sig_map = {s[0]: s for s in signals}

        # Exits: sell bearish positions at (close+low)/2
        for sym in list(self.positions.keys()):
            sig = sig_map.get(sym)
            if sig is None:
                continue
            _, ind_a, ind_b, high, low, close, avg_vol, strength = sig
            if ind_a < ind_b:
                self._sell(sym, d, (close + low) / 2)

        # Entries: buy top bullish signals at (close+high)/2
        needed = self.config.n_symbols - len(self.positions)
        if needed > 0 and self.cash > 1_000:
            candidates = [
                sig for sig in signals
                if sig[1] > sig[2] and sig[0] not in self.positions
            ][:needed]

            # Volume filter
            if self.config.volume_filter_pct > 0 and candidates:
                filtered = []
                for sig in candidates:
                    sym, ind_a, ind_b, high, low, close, avg_vol, strength = sig
                    if avg_vol > 0 and high > 0:
                        alloc_est = self.cash / len(candidates)
                        est_qty = int(alloc_est / high)
                        if est_qty > 0 and avg_vol > 0:
                            if est_qty / avg_vol > self.config.volume_filter_pct:
                                continue
                    filtered.append(sig)
                candidates = filtered

            if candidates:
                alloc_per = self.cash / len(candidates)
                for sig in candidates:
                    sym = sig[0]
                    high = sig[3]
                    close = sig[5]
                    if self.cash < 100:
                        break
                    self._buy(sym, d, (close + high) / 2, alloc_per)

        # Daily snapshot
        pos_val = 0.0
        for sym, pos in self.positions.items():
            if sym in sig_map:
                p = sig_map[sym][5]  # close price
                if pos.avg_price > 0 and abs(p / pos.avg_price - 1) > self.config.max_daily_move:
                    p = price_at(self.arrays, sym, d_ord) or pos.avg_price
            else:
                p = price_at(self.arrays, sym, d_ord) or pos.avg_price
            pos_val += pos.market_value(p)

        self.snapshots.append(DailySnapshot(
            date=str(d), cash=self.cash,
            positions_value=pos_val,
            total_value=self.cash + pos_val,
        ))

    def run(self, trading_dates: List[date],
            signals_cache: Optional[Dict[int, List[tuple]]] = None,
            signals_fn: Optional[Callable] = None):
        """
        Run backtest over trading_dates.

        Priority:
          1. signals_cache (pre-computed dict keyed by date ordinal)
          2. signals_fn(arrays, d_ord, config) called on the fly
          3. default: compute_sma_signals

        SIP: if config.sip_amount > 0, cash is added on the first
             trading day of each calendar month.
        """
        fn = signals_fn or compute_sma_signals
        last_sip_month = None

        for d in tqdm(trading_dates, desc="Simulating"):
            # SIP injection — first trading day of each month
            if self.config.sip_amount > 0:
                month_key = (d.year, d.month)
                if last_sip_month != month_key:
                    self.cash += self.config.sip_amount
                    last_sip_month = month_key

            if signals_cache is not None:
                signals = signals_cache.get(d.toordinal(), [])
            else:
                signals = fn(self.arrays, d.toordinal(), self.config)
            self.step(d, signals)
