from datetime import date
from typing import Dict, List

import numpy as np

from .types import Trade


def calc_xirr(start: date, end: date, initial: float, final: float) -> float:
    t = (end - start).days / 365.0
    if t <= 0 or initial <= 0 or final <= 0:
        return float('nan')
    return (final / initial) ** (1.0 / t) - 1.0


def compute_metrics(bt, start_d: date, end_d: date, initial_cash: float) -> dict:
    """Compute performance metrics for a completed backtest run."""
    snaps = bt.snapshots
    if not snaps:
        return {}

    values  = [s.total_value for s in snaps]
    initial = initial_cash
    final   = values[-1]

    total_return = (final - initial) / initial * 100

    xirr_rate = calc_xirr(start_d, end_d, initial, final)
    xirr_pct  = xirr_rate * 100 if np.isfinite(xirr_rate) else float('nan')

    # Max drawdown
    peak, max_dd = initial, 0.0
    for v in values:
        peak   = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak * 100)

    # Annualised Sharpe (risk-free rate = 0)
    rets = np.diff(values) / np.array(values[:-1])
    sharpe = (
        float(rets.mean() / rets.std() * np.sqrt(252))
        if len(rets) > 1 and rets.std() > 0
        else 0.0
    )

    # Win rate from round-trip P&L
    open_buys: Dict[str, Trade] = {}
    pnls: List[float] = []
    for t in bt.trades:
        if t.action == "BUY":
            open_buys[t.symbol] = t
        elif t.action == "SELL":
            b = open_buys.pop(t.symbol, None)
            if b:
                pnl = (t.execution_price - b.execution_price) * t.qty - b.cost - t.cost
                pnls.append(pnl)

    win_rate = (sum(1 for p in pnls if p > 0) / len(pnls) * 100) if pnls else 0.0

    return dict(
        start_date=str(start_d),
        end_date=str(end_d),
        n_trading_days=len(snaps),
        final_value=final,
        total_return=total_return,
        xirr_pct=xirr_pct,
        max_drawdown=max_dd,
        sharpe=sharpe,
        total_trades=len(bt.trades),
        win_rate=win_rate,
    )
