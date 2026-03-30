from dataclasses import dataclass


@dataclass
class TransactionCosts:
    # Variable fees (as % of trade value)
    stt_pct: float = 0.1           # STT: 0.1% on BUY and SELL
    exchange_pct: float = 0.00322  # NSE exchange txn charge
    sebi_pct: float = 0.0001       # SEBI turnover fee
    stamp_duty_pct: float = 0.015  # Stamp duty: 0.015% (BUY only)

    # GST
    gst_pct: float = 18.0          # 18% on (brokerage + exchange + SEBI)
    brokerage: float = 0.0         # Rs.0 for delivery

    # Fixed charges
    dp_charge: float = 15.93       # Flat Rs.15.93 per stock sold (SELL only)

    # Slippage
    slippage_pct: float = 0.0      # 0 — slippage modelled via (close+high)/2 buy and (close+low)/2 sell prices


def calc_buy_cost(price: float, qty: int, tc: TransactionCosts) -> tuple:
    """Returns (total_fees, slippage_adjusted_price)."""
    trade_value = price * qty
    stt      = trade_value * (tc.stt_pct / 100)
    exchange = trade_value * (tc.exchange_pct / 100)
    sebi     = trade_value * (tc.sebi_pct / 100)
    stamp    = trade_value * (tc.stamp_duty_pct / 100)
    gst      = (tc.brokerage + exchange + sebi) * (tc.gst_pct / 100)
    total_fees = stt + exchange + sebi + stamp + gst
    slippage_price = price * (1 + tc.slippage_pct / 100)
    return total_fees, slippage_price


def calc_sell_cost(price: float, qty: int, tc: TransactionCosts) -> tuple:
    """Returns (total_fees, slippage_adjusted_price)."""
    trade_value = price * qty
    stt      = trade_value * (tc.stt_pct / 100)
    exchange = trade_value * (tc.exchange_pct / 100)
    sebi     = trade_value * (tc.sebi_pct / 100)
    gst      = (tc.brokerage + exchange + sebi) * (tc.gst_pct / 100)
    dp       = tc.dp_charge
    total_fees = stt + exchange + sebi + gst + dp
    slippage_price = price * (1 - tc.slippage_pct / 100)
    return total_fees, slippage_price
