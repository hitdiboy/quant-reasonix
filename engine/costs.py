"""实盘模拟成本 — 佣金/印花税/过户费/滑点"""

def calc_commission(price: float, shares: int, rate: float = 0.0003, min_fee: float = 5.0) -> float:
    """计算佣金，含最低5元限制"""
    fee = price * shares * rate
    return max(fee, min_fee)

def calc_stamp_duty(price: float, shares: int, is_sell: bool = True, rate: float = 0.0005) -> float:
    """印花税，卖出时收0.05%"""
    if not is_sell:
        return 0.0
    return price * shares * rate

def calc_transfer_fee(price: float, shares: int, rate: float = 0.00001) -> float:
    """过户费，万0.1，买卖都收"""
    return price * shares * rate

def calc_slippage(price: float, side: str = "buy", rate: float = 0.001) -> float:
    """滑点：买入向上滑，卖出向下滑"""
    if side == "sell":
        return price * (1 - rate)
    return price * (1 + rate)

def calc_total_cost(price, shares, side="buy", commission_rate=0.0003, min_commission=5.0, stamp_duty_rate=0.0005, transfer_fee_rate=0.00001, slippage_rate=0.001):
    exec_price = calc_slippage(price, side, slippage_rate)
    comm = calc_commission(exec_price, shares, commission_rate, min_commission)
    stamp = calc_stamp_duty(exec_price, shares, side == "sell", stamp_duty_rate)
    trans = calc_transfer_fee(exec_price, shares, transfer_fee_rate)
    total_fee = comm + stamp + trans
    return {
        "exec_price": round(exec_price, 3),
        "commission": round(comm, 2),
        "stamp_duty": round(stamp, 2),
        "transfer_fee": round(trans, 2),
        "total_fee": round(total_fee, 2),
        "net_amount": round(exec_price * shares + (total_fee if side == "buy" else -total_fee), 2),
    }

def calc_shares_by_cash(cash: float, price: float, min_unit: int = 100) -> int:
    max_shares = int(cash / price)
    return (max_shares // min_unit) * min_unit

def calc_shares_by_position(position: int, min_unit: int = 100) -> int:
    return (position // min_unit) * min_unit

def market_is_sh(code: str) -> bool:
    c = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    return c.startswith("6")

def get_price_limit(code: str) -> float:
    c = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if c.startswith("30") or c.startswith("68"):
        return 0.20
    if c.startswith("8"):
        return 0.30
    return 0.10

def check_limit_up_down(close: float, prev_close: float, code: str) -> tuple:
    if prev_close <= 0:
        return False, False
    limit = get_price_limit(code)
    limit_up = round(prev_close * (1 + limit), 2)
    limit_down = round(prev_close * (1 - limit), 2)
    return (close >= limit_up, close <= limit_down)

def calc_position_limit(cash: float, max_single_pct: float = 0.2) -> float:
    return cash * max_single_pct