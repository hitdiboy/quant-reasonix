# -*- coding: utf-8 -*-
"""龙首阴策略 v40 — 选股增强版

基于全量回测（200只）的交易数据深度挖掘发现：
1. 连板期间成交量的形态是关键——真正有第二波的股票，连板期间是"放量上涨"
2. 首阴当天的缩量程度是质量指标——缩量≤0.7均量的信号后续胜率极高
3. 连板起点价格低（<20元）的标的弹性更大

v40 在 v38 基础上新增：
- 连板期间质量评分（量价配合度）
- 首阴缩量硬门槛（≤1.0均量，否则评分打折）
- 价格区间过滤（低价股偏好）
- 信号评分 < 50 直接跳过
"""
from strategies._base import BaseStrategy
import numpy as np
import pandas as pd


class DragonFirstYinV40(BaseStrategy):
    name = "龙首阴v40"
    description = "龙首阴v40-选股增强版(量价评分+缩量硬门槛)"
    custom_id = "C006"

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

    # 选股增强参数
    min_signal_score = 50       # 信号评分低于此值不入场
    max_entry_price = 50.0      # 股价高于此值减仓
    prefer_low_price = True     # 优先低价股

    # 出场参数（v38 优化版）
    trail_dd_pct = 8.0
    trail_atr_mult = 3.0
    stop_loss_pct = -12.0
    take_profit_pct = 25.0
    time_stop_days = 15
    grace_period_days = 3

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

        # 涨停连板计数
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

        # 量MA20（用于连板期间量比分析）
        self.vol_ma20_arr = vol_s.rolling(20).mean().values
        self.vol_ma20 = self.I(lambda: self.vol_ma20_arr, name="VolMA20")

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

    def _calc_score(self, streak, vol_ratio, yin_depth, atr_ratio, is_fake, streak_vol_ratio):
        """增强版评分：加入连板期间量比和价格因素"""
        s = 0.0
        # 连板强度
        if streak >= 5: s += 25
        elif streak == 4: s += 22
        elif streak >= 3: s += 18
        else: s += 12
        # 首阴缩量（核心）
        if vol_ratio <= 0.3: s += 25
        elif vol_ratio <= 0.5: s += 20
        elif vol_ratio <= 0.7: s += 15
        elif vol_ratio <= 1.0: s += 8
        # 假阴线加分
        if is_fake: s += 15
        # 阴线深度
        if yin_depth >= 0: s += 15
        elif yin_depth >= -2: s += 12
        elif yin_depth >= -4: s += 8
        elif yin_depth >= -6: s += 4
        # ATR比例
        if atr_ratio <= 0.03: s += 15
        elif atr_ratio <= 0.06: s += 10
        elif atr_ratio <= 0.10: s += 5
        # 连板量比（放量连板加分——真实买盘）
        if streak_vol_ratio > 0:
            if streak_vol_ratio >= 2.0: s += 10
            elif streak_vol_ratio >= 1.5: s += 5
        return min(s, 100.0)

    def next(self):
        if len(self.data) < max(self.atr_period, 30) + 1:
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
        vol_ma20_val = float(self.vol_ma20[-1])
        streak_prev = int(self.streak[-2])
        streak_cur = int(self.streak[-1])
        is_yin = bool(self.is_yin[-1])
        is_fake_yin = bool(self._is_fake_yin_arr[cur_idx]) if cur_idx < len(self._is_fake_yin_arr) else False

        # ---- 入场 ----
        if (streak_prev >= self.min_limit_ups
            and not (streak_cur >= 1 and close / prev_close - 1 >= self._limit_up)
            and is_yin
            and not self.position):

            # 基础过滤
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

            if not_limit_down and vol_ok and atr_ok and depth_ok:
                # 连板期间的平均量比（相对20日均量）
                streak_start = cur_idx - streak_prev
                streak_vols = self._s_vol[max(0, streak_start):cur_idx]
                streak_vol_ratio = np.mean(streak_vols) / vol_ma20_val if vol_ma20_val > 0 else 0

                score = self._calc_score(streak_prev, vol_ratio, yin_depth, atr_ratio, is_fake_yin, streak_vol_ratio)

                # 评分硬门槛
                if score >= self.min_signal_score:
                    if vol_ratio <= 0.7:
                        score = min(100.0, score + 10)

                    if score >= 80: entry_pct = self.max_entry_pct
                    elif score >= 65: entry_pct = self.base_entry_pct * 1.5
                    elif score >= 50: entry_pct = self.base_entry_pct
                    else: entry_pct = self.base_entry_pct * 0.5

                    # 高价股减仓
                    if self.prefer_low_price and close > self.max_entry_price:
                        entry_pct *= 0.5

                    n_shares = int(self.equity * entry_pct / close / 100) * 100
                    if n_shares >= 100:
                        self.buy(size=n_shares)
                        self._entry_price = close
                        self._entry_bar = cur_idx
                        self._trail_high = close
                        return

        # ---- 持仓管理（同 v38）----
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