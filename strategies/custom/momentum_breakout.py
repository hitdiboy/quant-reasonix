# -*- coding: utf-8 -*-
"""动量突破策略 — 与龙首阴互补（趋势市）"""
from strategies._base import BaseStrategy
import numpy as np


class MomentumBreakout(BaseStrategy):
    name = "动量突破"
    description = "动量突破-20日高点突破+量能确认"
    custom_id = "C009"

    stock_code = ""
    allowed_boards = ["创业板", "中小板", "科创板"]

    # 参数
    breakout_period = 20
    vol_multiplier = 1.5
    atr_period = 14
    base_entry_pct = 0.15

    # 出场
    trail_dd_pct = 7.0
    stop_loss_pct = -8.0
    time_stop_days = 10

    def init(self):
        close_s = self.data.Close.to_series()
        high_s = self.data.High.to_series()
        vol_s = self.data.Volume.to_series()
        n = len(close_s)

        # 20日最高价
        self.breakout_high = self.I(lambda: high_s.rolling(self.breakout_period).max().values, name="BreakoutHigh")
        # ATR
        tr = np.maximum(high_s - self.data.Low.to_series(),
                        np.maximum(abs(high_s - close_s.shift(1)),
                                   abs(self.data.Low.to_series() - close_s.shift(1))))
        tr.iloc[0] = 0
        self.atr_arr = tr.rolling(self.atr_period).mean().values
        self.atr = self.I(lambda: self.atr_arr, name="ATR")
        # 均量
        self.vol_ma20 = self.I(lambda: vol_s.rolling(20).mean().values, name="VolMA20")

        self._entry_bar = None
        self._entry_price = 0.0
        self._trail_high = 0.0

    def next(self):
        if len(self.data) < max(self.breakout_period, self.atr_period) + 1:
            return
        cur_idx = len(self.data) - 1
        close = float(self.data.Close[-1])
        volume = float(self.data.Volume[-1])
        atr_val = float(self.atr[-1])
        vol_ma20_val = float(self.vol_ma20[-1])
        breakout_val = float(self.breakout_high[-1])

        # 入场：突破20日高点 + 放量确认
        if (close >= breakout_val
            and volume >= vol_ma20_val * self.vol_multiplier
            and not self.position):

            n_shares = int(self.equity * self.base_entry_pct / close / 100) * 100
            if n_shares >= 100:
                self.buy(size=n_shares)
                self._entry_price = close
                self._entry_bar = cur_idx
                self._trail_high = close
                return

        # 持仓管理
        if self.position and self._entry_bar is not None:
            bars_held = cur_idx - self._entry_bar
            self._trail_high = max(self._trail_high, close)
            profit_pct = (close - self._entry_price) / self._entry_price * 100

            dd_from_peak = (self._trail_high - close) / self._trail_high * 100
            if dd_from_peak >= self.trail_dd_pct:
                self.position.close()
                return
            if profit_pct <= self.stop_loss_pct:
                self.position.close()
                return
            if bars_held >= self.time_stop_days:
                self.position.close()
                return