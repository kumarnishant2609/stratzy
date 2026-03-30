"""
SMA Crossover Momentum Trading Strategy

Strategy logic:
- Calculate a short SMA and a long SMA on closing prices for every stock
- If short SMA > long SMA -> stock has upward momentum -> bullish signal
- If short SMA < long SMA -> stock has downward momentum -> bearish signal
- Rank buy candidates by (short_sma - long_sma) / price  (signal strength)
- Hold at most n_symbols positions at a time
- Exit a position when its stock turns bearish
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from tqdm import tqdm

from .base import BaseStrategy
from ..models.signals import SignalData
from ..models.portfolio import Portfolio, Position


@dataclass
class SMAConfig:
    long_sma: int = 140              # slow moving average window (days)
    short_sma: int = 120             # fast moving average window (days)
    n_symbols: int = 5               # max positions to hold at once
    initial_cash: float = 100_000.0
    min_cash_threshold: float = 1_000.0
    data_lookback_days: int = 250    # must be > long_sma
    volume_filter_pct: float = 0.05  # max order size as % of avg daily volume
    slippage_tolerance: float = 0.005  # 0.5% limit-order slippage


class SMAStrategy(BaseStrategy):
    """SMA Crossover Momentum Strategy"""

    def __init__(self, config: SMAConfig, data_client):
        super().__init__(data_client)
        self.config = config

    def calculate_signals(self, symbols: List[str]) -> List[SignalData]:
        """
        Compute SMA signals for every symbol.

        SignalData mapping:
          indicator_a  = short SMA
          indicator_b  = long SMA
          signal_strength = (short_sma - long_sma) / price
        """
        signals = []
        print(f"Calculating SMA signals for {len(symbols)} symbols...")

        for symbol in tqdm(symbols):
            try:
                symbol_data = self.data_client.get_symbol_data(
                    symbol, self.config.data_lookback_days
                )
                closes = symbol_data.closes

                short_sma = symbol_data.get_latest_sma(self.config.short_sma)
                long_sma  = symbol_data.get_latest_sma(self.config.long_sma)

                if short_sma is None or long_sma is None or len(closes) == 0:
                    continue

                current_price = float(closes[-1])
                if current_price <= 0:
                    continue

                signal_strength = (short_sma - long_sma) / current_price

                signals.append(SignalData(
                    symbol=symbol,
                    indicator_a=short_sma,
                    indicator_b=long_sma,
                    current_price=current_price,
                    high_price=float(symbol_data.highs[-1]),
                    low_price=float(symbol_data.lows[-1]),
                    signal_strength=signal_strength,
                    average_volume=symbol_data.get_average_volume(30),
                ))

            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue

        signals.sort(key=lambda x: x.signal_strength, reverse=True)
        print(f"SMA computed for {len(signals)} symbols")
        return signals

    def get_bullish_signals(self, signals: List[SignalData]) -> List[SignalData]:
        return [s for s in signals if s.is_bullish]

    def check_exit_signals(self, signals: List[SignalData]) -> List[str]:
        if not self.portfolio or not self.portfolio.positions:
            return []
        sig_map = {s.symbol: s for s in signals}
        to_exit = []
        for symbol in self.portfolio.positions:
            sig = sig_map.get(symbol)
            if sig and sig.is_bearish:
                print(f"Exit: {symbol}  short_sma={sig.indicator_a:.2f} < long_sma={sig.indicator_b:.2f}")
                to_exit.append(symbol)
        return to_exit

    def execute_sell(self, symbol: str, dry_run: bool = True):
        if symbol not in self.portfolio.positions:
            return
        position     = self.portfolio.positions[symbol]
        symbol_data  = self.data_client.get_symbol_data(symbol, 2)
        current_price = float(symbol_data.closes[-1])
        limit_price  = round(current_price * (1 - self.config.slippage_tolerance) * 20) / 20
        sale_value   = position.quantity * limit_price

        if dry_run:
            print(f"[DRY RUN] LIMIT SELL {position.quantity} x {symbol} @ min Rs.{limit_price:.2f} = Rs.{sale_value:.2f}")
        else:
            print(f"[LIVE] Placing LIMIT SELL {position.quantity} x {symbol} @ Rs.{limit_price:.2f}")
            try:
                self.data_client.place_order(
                    symbol=symbol, action="SELL",
                    quantity=position.quantity, price=limit_price,
                )
            except Exception as e:
                print(f"Order failed: {e}")
                return

        self.portfolio.cash += sale_value
        del self.portfolio.positions[symbol]

    def execute_buy(self, symbol: str, max_cash: float,
                    current_price: float, dry_run: bool = True) -> float:
        limit_price = round(current_price * (1 + self.config.slippage_tolerance) * 20) / 20
        quantity    = int(max_cash / limit_price)
        if quantity <= 0:
            return 0.0
        cost = quantity * limit_price

        if dry_run:
            print(f"[DRY RUN] LIMIT BUY  {quantity} x {symbol} @ max Rs.{limit_price:.2f} = Rs.{cost:.2f}")
        else:
            print(f"[LIVE] Placing LIMIT BUY {quantity} x {symbol} @ Rs.{limit_price:.2f}")
            try:
                self.data_client.place_order(
                    symbol=symbol, action="BUY",
                    quantity=quantity, price=limit_price,
                )
            except Exception as e:
                print(f"Order failed: {e}")
                return 0.0

        self.portfolio.positions[symbol] = Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=limit_price,
            purchase_date=datetime.now().strftime("%Y-%m-%d"),
        )
        self.portfolio.cash -= cost
        return cost

    def rebalance_portfolio(self, signals: List[SignalData], dry_run: bool = True):
        print("\n" + "=" * 60)
        print("REBALANCING PORTFOLIO  [SMA CROSSOVER]")
        print("=" * 60)

        # Exits
        to_exit = self.check_exit_signals(signals)
        print(f"\nExiting {len(to_exit)} bearish positions...")
        for symbol in to_exit:
            self.execute_sell(symbol, dry_run=dry_run)

        # Entries
        bullish    = self.get_bullish_signals(signals)
        candidates = [s for s in bullish if s.symbol not in self.portfolio.positions]
        needed     = self.config.n_symbols - len(self.portfolio.positions)

        print(f"\nPositions: {len(self.portfolio.positions)}/{self.config.n_symbols}  "
              f"|  Cash: Rs.{self.portfolio.cash:.2f}")
        if needed <= 0:
            print("Portfolio full.")
            return
        to_buy = min(needed, len(candidates))
        if to_buy == 0:
            print("No bullish candidates.")
            return

        cash_per = self.portfolio.cash / to_buy
        print(f"Buying top {to_buy} signals (Rs.{cash_per:.2f} each)...")

        for sig in candidates[:to_buy]:
            if self.portfolio.cash < self.config.min_cash_threshold:
                break
            # Ghost stock filter — skip if our order would be > 5% of avg daily volume
            est_qty = int(cash_per / sig.current_price) if sig.current_price > 0 else 0
            if est_qty > 0:
                required_vol = est_qty / self.config.volume_filter_pct
                if sig.average_volume < required_vol:
                    print(f"Skipping {sig.symbol}: ghost stock risk "
                          f"(avg vol {sig.average_volume:,.0f})")
                    continue
            self.execute_buy(sig.symbol, cash_per, sig.current_price, dry_run=dry_run)

    def run_strategy(self, dry_run: bool = True):
        print("\n" + "=" * 60)
        print("SMA CROSSOVER MOMENTUM STRATEGY")
        print("=" * 60)
        print(f"Date:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Short SMA: {self.config.short_sma} days")
        print(f"Long SMA:  {self.config.long_sma} days")
        print(f"Hold:      {self.config.n_symbols} symbols")
        print(f"Mode:      {'DRY RUN' if dry_run else 'LIVE TRADING'}")
        print("=" * 60)

        # Load / init portfolio
        self.portfolio = Portfolio.load()
        if self.portfolio is None:
            print(f"\nNew portfolio — Rs.{self.config.initial_cash:.2f}")
            self.portfolio = Portfolio(cash=self.config.initial_cash, positions={})
        else:
            print(f"\nLoaded portfolio — Cash: Rs.{self.portfolio.cash:.2f}  "
                  f"Positions: {len(self.portfolio.positions)}")

        # Load symbol universe
        print("\nLoading symbols...")
        symbols = self.data_client.get_all_symbols()
        print(f"Universe: {len(symbols)} symbols")

        # Compute signals
        signals = self.calculate_signals(symbols)

        # Display top 10 bullish
        bullish = self.get_bullish_signals(signals)
        print(f"\nTop 10 Bullish SMA Signals ({len(bullish)} total):")
        print(f"{'#':<5} {'Symbol':<15} {'Short SMA':<12} {'Long SMA':<12} {'Strength':<12} {'Price':<10}")
        print("-" * 66)
        for i, s in enumerate(bullish[:10], 1):
            print(f"{i:<5} {s.symbol:<15} {s.indicator_a:<12.2f} "
                  f"{s.indicator_b:<12.2f} {s.signal_strength:<12.4f} {s.current_price:<10.2f}")

        # Rebalance
        self.rebalance_portfolio(signals, dry_run=dry_run)

        # Summary
        print("\n" + "=" * 60)
        print("PORTFOLIO SUMMARY")
        print("=" * 60)
        print(f"Cash: Rs.{self.portfolio.cash:.2f}")
        if self.portfolio.positions:
            sig_map = {s.symbol: s for s in signals}
            print(f"\n{'Symbol':<15} {'Qty':<8} {'Avg Price':<12} {'Current':<12} {'P&L %':<10}")
            print("-" * 60)
            for sym, pos in self.portfolio.positions.items():
                sig = sig_map.get(sym)
                cp  = sig.current_price if sig else pos.avg_price
                pnl_pct = ((cp - pos.avg_price) / pos.avg_price * 100) if pos.avg_price > 0 else 0
                print(f"{sym:<15} {pos.quantity:<8} {pos.avg_price:<12.2f} {cp:<12.2f} {pnl_pct:<10.2f}")

        total = self.portfolio.total_value({s.symbol: s.current_price for s in signals})
        print(f"\nTotal Portfolio Value: Rs.{total:.2f}")

        self.portfolio.save()
        print("\nStrategy execution complete.")
