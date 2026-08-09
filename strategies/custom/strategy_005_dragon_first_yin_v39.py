# -*- coding: utf-8 -*-
"""龙首阴策略 v39 — 趋势过滤版

基于全量回测(200只)的赢家/输家特征分析发现：
- 赢家共性：信号发生时股价在 MA60 上方（中期多头）
- 输家共性：信号发生时股价在 MA60 下方（中期空头）

v39 仅在 MA60 多头排列时入场，预期大幅提升胜率。
"""
from strategies._base import BaseStrategy
import numpy as np
import pandas as pd


class DragonFirstYinV39(BaseStrategy):
    name = "龙首阴v39"
    description = "龙首阴v39-趋势过滤版(MA60多头+参数优化)"
    custom_id = "C005"

    stock_code = ""
    allowed_boards = ["创业板", "中小板", "科创板"]

    @staticmethod
    def classify_board(code):
        if code.startswith("688"): return "科创板"
        if code.startswith("300"): return "创业板"
        if code.startswith("002"): return "中小板"
        return "其他"

    @staticmethod
    def get_limit_threshold(board):
        return 0.198 if board in ("创业板", "科创板") else 0.098

    # 入场参数
    min_limit_ups = 2
    max_vol_ratio = 2.5
    atr_ratio_limit = 0.25
    yin_depth_pct = -12.0
    atr_period = 14
    base_entry_pct = 0.10
    max_entry_pct = 0.25

    # 趋势过滤
    use_trend_filter = True       # MA60 多头过滤（核心改进）
    trend_ma_period = 60

    # 出场参数（v38 优化版）
    trail_dd_pct = 8.0
    trail_atr_mult = 3.0
    stop_loss_pct = -12.0
    take_profit_pct = 25.0
    time_stop_days = 15
    grace_period_days = 3

    # 开关
    use_signal_scoring = True
    prefer_shrink_volume = True

    def init(self):
        close_s = self.data.Close.to_series()
        high_s = self.data.High.to_series()
        low_s = self.data.Low.to_series()
        vol_s = self.data.Volume.to_series()
        open_s = self.data.Open.to_series()
        n = len(close_s)

        if self.stock_code:
            board = self.classify_board(self.stock_code)
            self._limit_up = self.get_limit_threshold(board)
            self._limit_down = self._limit_up
        else:
            self._limit_up = 0.098
            self._limit_down = 0.098

        # 涨停连续计数
        streak_arr = np.zeros(n)
        cnt = 0
        for i in range(1, n):
            if close_s.iloc[i] / close_s.iloc[i-1] - 1 >= self._limit_up:
                cnt += 1
            else:
                cnt = 0
            streak_arr[i] = cnt
        self.streak_arr = streak_arr
        self.streak = self.I(lambda: self.streak_arr, name="LimitStreak")

        # 阴线信号
        is_real_yin = (close_s < open_s).values.astype(bool)
        is_fake_yin = ((close_s > close_s.shift(1)) & (close_s < open_s)).values.astype(bool)
        self._is_real_yin_arr = is_real_yin
        self._is_fake_yin_arr = is_fake_yin
        self.is_yin = self.I(lambda: is_real_yin | is_fake_yin, name="IsYin")

        # ATR
        tr = np.maximum(high_s - low_s,
                        np.maximum(abs(high_s - close_s.shift(1)),
                                   abs(low_s - close_s.shift(1))))
        tr.iloc[0] = 0
        self.atr_arr = tr.rolling(self.atr_period).mean().values
        self.atr = self.I(lambda: self.atr_arr, name="ATR")

        # 量MA5
        self.vol_ma5_arr = vol_s.rolling(5).mean().values
        self.vol_ma5 = self.I(lambda: self.vol_ma5_arr, name="VolMA5")

        # MA60 趋势过滤
        self.ma60_arr = close_s.rolling(self.trend_ma_period).mean().values
        self.ma60 = self.I(lambda: self.ma60_arr, name="MA60")

        # K线数据
        self._s_close = close_s.values
        self._s_high = high_s.values
        self._s_low = low_s.values
        self._s_vol = vol_s.values
        self._s_open = open_s.values

        self._entry_bar = None
        self._entry_price = 0.0
        self._trail_high = 0.0

        self._board_ok = True
        if self.stock_code:
            board = self.classify_board(self.stock_code)
            self._board_ok = board in self.allowed_boards
            self._cur_board = board

    def _calc_score(self, streak, vol_ratio, yin_depth, atr_ratio, is_fake):
        s = 0.0
        if streak >= 5: s += 30
        elif streak == 4: s += 27
        elif streak >= 3: s += 22
        else: s += 15
        if vol_ratio <= 0.3: s += 25
        elif vol_ratio <= 0.5: s += 20
        elif vol_ratio <= 0.7: s += 15
        elif vol_ratio <= 1.2: s += 8
        if is_fake: s += 15
        if yin_depth >= 0: s += 15
        elif yin_depth >= -2: s += 12
        elif yin_depth >= -4: s += 8
        elif yin_depth >= -6: s += 4
        if atr_ratio <= 0.03: s += 15
        elif atr_ratio <= 0.06: s += 10
        elif atr_ratio <= 0.10: s += 5
        return min(s, 100.0)

    def next(self):
        if len(self.data) < max(self.atr_period, self.trend_ma_period, 30) + 1:
            return
        if not self._board_ok:
            return

        cur_idx = len(self.data) - 1
        close = float(self.data.Close[-1])
        prev_close = float(self.data.Close[-2])
        volume = float(self.data.Volume[-1])
        atr_val = float(self.atr[-1])
        atr_ratio = atr_val / close if close > 0 else 1
        vol_ma5_val = float(self.vol_ma5[-1])
        ma60_val = float(self.ma60[-1])
        streak_prev = int(self.streak[-2])
        streak_cur = int(self.streak[-1])
        is_yin = bool(self.is_yin[-1])
        is_fake_yin = bool(self._is_fake_yin_arr[cur_idx]) if cur_idx < len(self._is_fake_yin_arr) else False

        # ---- 入场 ----
        if (streak_prev >= self.min_limit_ups
            and not (streak_cur >= 1 and close / prev_close - 1 >= self._limit_up)
            and is_yin
            and not self.position):

            # ★ 趋势过滤：收盘价在 MA60 上方（中期多头）
            trend_ok = not self.use_trend_filter or close > ma60_val

            not_limit_down = close > prev_close * (1 - self._limit_down - 0.005)
            vol_ratio = volume / vol_ma5_val if vol_ma5_val > 0 else 99
            vol_ok = volume <= vol_ma5_val * self.max_vol_ratio if vol_ma5_val > 0 else True
            atr_ok = atr_val > 0 and atr_ratio < self.atr_ratio_limit

            yin_depth = 0
            depth_ok = True
            if streak_prev >= 1:
                limit_close = float(self.data.Close[-(streak_prev + 1)])
                yin_depth = (close - limit_close) / limit_close * 100
                depth_ok = yin_depth >= self.yin_depth_pct

            if trend_ok and not_limit_down and vol_ok and atr_ok and depth_ok:
                score = self._calc_score(streak_prev, vol_ratio, yin_depth, atr_ratio, is_fake_yin)
                if vol_ratio <= 0.7 and self.prefer_shrink_volume:
                    score = min(100.0, score + 10)
                if score >= 80: entry_pct = self.max_entry_pct
                elif score >= 65: entry_pct = self.base_entry_pct * 1.5
                elif score >= 50: entry_pct = self.base_entry_pct
                else: entry_pct = self.base_entry_pct * 0.5

                n_shares = int(self.equity * entry_pct / close / 100) * 100
                if n_shares >= 100:
                    self.buy(size=n_shares)
                    self._entry_price = close
                    self._entry_bar = cur_idx
                    self._trail_high = close
                    return

        # ---- 持仓管理 ----
        if self.position and self._entry_bar is not None:
            bars_held = cur_idx - self._entry_bar
            self._trail_high = max(self._trail_high, close)
            profit_pct = (close - self._entry_price) / self._entry_price * 100

            if profit_pct >= self.take_profit_pct and self.position.size > 100:
                self.sell(size=self.position.size // 2)
                self._trail_high = close
                return

            if bars_held >= self.grace_period_days and self._trail_high > self._entry_price:
                dd_from_peak = (self._trail_high - close) / self._trail_high * 100
                atr_from_peak = (self._trail_high - close) / atr_val if atr_val > 0 else 999
                if dd_from_peak >= self.trail_dd_pct or atr_from_peak >= self.trail_atr_mult:
                    self.position.close()
                    return

            if profit_pct <= self.stop_loss_pct:
                self.position.close()
                return
            if bars_held >= self.time_stop_days:
                self.position.close()
                return