# -*- coding: utf-8 -*-
"""尾盘隔夜超短战法 — 策略实现"""
from strategies._base import BaseStrategy
import numpy as np


class EndOfDayBreakout(BaseStrategy):
    name = "尾盘隔夜战法"
    description = "尾盘隔夜超短-放量突破+多头排列+次日冲高卖出"
    custom_id = "C010"

    stock_code = ""
    allowed_boards = ["创业板", "中小板", "科创板"]

    min_volume_ratio = 1.5
    min_close_position = 0.667
    min_body_ratio = 0.3
    require_up_day = True
    require_ma20 = True
    require_ma60 = False
    base_entry_pct = 0.20
    profit_target_pct = 2.0
    stop_loss_pct = -2.0
    max_hold_bars = 1

    @staticmethod
    def classify_board(code):
        if code.startswith("688"): return "科创板"
        if code.startswith("300"): return "创业板"
        if code.startswith("002"): return "中小板"
        return "其他"

    def init(self):
        close_s = self.data.Close.to_series()
        high_s = self.data.High.to_series()
        low_s = self.data.Low.to_series()
        open_s = self.data.Open.to_series()
        vol_s = self.data.Volume.to_series()
        n = len(close_s)

        self.close_position = self.I(
            lambda: ((close_s - low_s) / (high_s - low_s).replace(0, np.nan)).values,
            name="ClosePos"
        )
        body = abs(close_s - open_s)
        self.body_ratio = self.I(
            lambda: (body / (high_s - low_s).replace(0, np.nan)).values,
            name="BodyRatio"
        )
        self.is_up_day = self.I(
            lambda: (close_s > open_s).values.astype(float),
            name="IsUpDay"
        )
        self.vol_ma5_arr = vol_s.rolling(5).mean().values
        self.vol_ma5 = self.I(lambda: self.vol_ma5_arr, name="VolMA5")
        self.ma20_arr = close_s.rolling(20).mean().values
        self.ma60_arr = close_s.rolling(60).mean().values
        self.ma20 = self.I(lambda: self.ma20_arr, name="MA20")
        self.ma60 = self.I(lambda: self.ma60_arr, name="MA60")

        self._s_open = open_s.values
        self._s_high = high_s.values
        self._s_low = low_s.values
        self._s_close = close_s.values
        self._s_vol = vol_s.values

        self._entry_bar = None
        self._entry_price = 0.0

    def next(self):
        if len(self.data) < 30:
            return

        cur_idx = len(self.data) - 1
        close = float(self.data.Close[-1])
        high = float(self.data.High[-1])
        low = float(self.data.Low[-1])
        open_ = float(self.data.Open[-1])
        volume = float(self.data.Volume[-1])
        vol_ma5_val = float(self.vol_ma5[-1])
        cp = float(self.close_position[-1])
        br = float(self.body_ratio[-1])
        is_up = bool(self.is_up_day[-1])
        ma20_val = float(self.ma20[-1])
        ma60_val = float(self.ma60[-1]) if not np.isnan(float(self.ma60[-1])) else 0

        # ---- 入场 ----
        if not self.position:
            vol_ok = volume >= vol_ma5_val * self.min_volume_ratio if vol_ma5_val > 0 else False
            pos_ok = cp >= self.min_close_position
            up_ok = is_up if self.require_up_day else True
            body_ok = br >= self.min_body_ratio
            ma20_ok = close > ma20_val if self.require_ma20 else True
            ma60_ok = close > ma60_val if self.require_ma60 and ma60_val > 0 else True

            if vol_ok and pos_ok and up_ok and body_ok and ma20_ok and ma60_ok:
                n_shares = int(self.equity * self.base_entry_pct / close / 100) * 100
                if n_shares >= 100:
                    self.buy(size=n_shares)
                    self._entry_price = close
                    self._entry_bar = cur_idx

        # ---- 出场(次日) ----
        if self.position and self._entry_bar is not None:
            bars_held = cur_idx - self._entry_bar
            if bars_held >= 1:
                profit_pct = (close - self._entry_price) / self._entry_price * 100
                if profit_pct >= self.profit_target_pct:
                    self.position.close()
                    return
                if profit_pct <= self.stop_loss_pct:
                    self.position.close()
                    return
                if bars_held >= self.max_hold_bars:
                    self.position.close()
                    return