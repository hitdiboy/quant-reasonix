# 风控校验模块

import pandas as _pd


def check_survival_bias(data: _pd.DataFrame, label: str = "") -> list:
    warnings = []
    if data.empty:
        warnings.append(f"[{label or '未知'}] 数据为空，无法校验")
    return warnings


def check_trading_costs(commission: float, slippage: float = 0.0, num_trades: int = 0, label: str = "") -> list:
    warnings = []
    if commission <= 0:
        warnings.append(f"[{label or '未知'}] 佣金为0，回测偏乐观")
    if slippage <= 0 and num_trades > 100:
        warnings.append(f"[{label or '未知'}] 滑点未设置，高频策略回测不可靠")
    return warnings


def check_position_concentration(weights: dict, max_single: float = 0.2, label: str = "") -> list:
    warnings = []
    for symbol, w in weights.items():
        if w > max_single:
            warnings.append(f"[{label or '未知'}] {symbol} 占比 {w:.1%}，超过上限 {max_single:.0%}")
    return warnings