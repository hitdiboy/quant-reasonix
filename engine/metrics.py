# 绩效指标计算

import numpy as _np


def calc_sharpe(returns: list, periods_per_year: int = 252) -> float:
    """年化夏普比率（无风险利率=0）"""
    if len(returns) < 2:
        return 0.0
    arr = _np.array(returns)
    return float(_np.sqrt(periods_per_year) * arr.mean() / arr.std()) if arr.std() > 0 else 0.0


def calc_max_drawdown(equity: list) -> dict:
    """最大回撤及持续时间"""
    arr = _np.array(equity)
    peak = _np.maximum.accumulate(arr)
    drawdown = (arr - peak) / peak
    idx = _np.argmin(drawdown)
    return {
        "max_dd_pct": float(abs(drawdown[idx]) * 100),
        "peak_value": float(peak[idx]),
        "trough_value": float(arr[idx]),
        "trough_index": int(idx),
    }


def extract_metrics(bt_result) -> dict:
    """从 backtesting.py 结果中提取标准指标"""
    return {
        "年化收益率%": round(bt_result.get("Return [%]", 0), 2),
        "年化收益%": round(bt_result.get("Return (Ann.) [%]", 0), 2),
        "年化波动%": round(bt_result.get("Volatility (Ann.) [%]", 0), 2),
        "夏普比率": round(bt_result.get("Sharpe Ratio", 0), 3),
        "最大回撤%": round(bt_result.get("Max. Drawdown [%]", 0), 2),
        "卡玛比率": round(bt_result.get("Calmar Ratio", 0), 3) if bt_result.get("Calmar Ratio") else 0,
        "胜率%": round(bt_result.get("Win Rate [%]", 0), 2),
        "盈亏比": round(bt_result.get("Profit Factor", 0), 3),
        "交易次数": int(bt_result.get("# Trades", 0)),
        "SQN": round(bt_result.get("SQN", 0), 3),
    }