"""实盘模拟规则 — T+1/涨跌停/停牌/部分成交"""

import pandas as pd
import numpy as np
from datetime import timedelta


def build_sim_columns(df: pd.DataFrame, code: str) -> pd.DataFrame:
    df = df.copy()
    df["prev_close"] = df["Close"].shift(1)
    df["prev_close"] = df["prev_close"].ffill()
    limit_pct = _get_limit_pct(code)
    df["limit_up"] = round(df["prev_close"] * (1 + limit_pct), 2)
    df["limit_down"] = round(df["prev_close"] * (1 - limit_pct), 2)
    df["is_limit_up"] = df["Close"] >= df["limit_up"]
    df["is_limit_down"] = df["Close"] <= df["limit_down"]
    return df


def _get_limit_pct(code: str) -> float:
    c = code.replace(".SH","").replace(".SZ","").replace(".BJ","")
    if c.startswith("30") or c.startswith("68"):
        return 0.20
    if c.startswith("8"):
        return 0.30
    return 0.10


class TPlusOneTracker:
    """T+1 跟踪器"""
    def __init__(self):
        self._buy_dates = {}
    def record_buy(self, code: str, date):
        self._buy_dates[code] = date
    def can_sell(self, code: str, current_date) -> bool:
        if code not in self._buy_dates:
            return True
        return current_date > self._buy_dates[code]
    def remove_position(self, code: str):
        self._buy_dates.pop(code, None)


def simulate_partial_fill(price, shares, volume, fill_rate=0.8):
    if volume <= 0:
        return 0, 0.0, False
    volume_ratio = shares / volume if volume > 0 else 1.0
    if volume_ratio < 0.01:
        fill = 1.0
    elif volume_ratio < 0.05:
        fill = fill_rate
    elif volume_ratio < 0.1:
        fill = fill_rate * 0.7
    else:
        fill = fill_rate * 0.4
    actual = int(shares * fill)
    actual = (actual // 100) * 100
    return actual, fill, actual >= shares


def check_stop_loss(current_value, peak_value, max_dd_pct=0.15):
    if peak_value <= 0:
        return False
    return (peak_value - current_value) / peak_value >= max_dd_pct


def check_concentration(pos_value, total_equity, max_pct=0.2):
    if total_equity <= 0:
        return False
    return (pos_value / total_equity) > max_pct