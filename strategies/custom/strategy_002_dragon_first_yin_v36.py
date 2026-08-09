# -*- coding: utf-8 -*-
"""龙首阴策略 v36 — 优化版

基于 quant-codex 项目5轮迭代经验和教训：
1. 移动止损优于固定ATR止损（科创板正占比22.2%→51.9%）
2. _apply_board_params() 覆盖用户参数（已修复）
3. 前复权扭曲历史涨停信号
4. MACD/KDJ/Index三过滤拦截率过高
5. 创业板/科创板20%与主板10%涨跌幅差异

主要优化：
- 自动按板适配涨停阈值（10%/20%）
- 简化过滤链，保留核心风控
- 默认跳过板参数覆盖
- 强化移动止损逻辑
"""

from strategies._base import BaseStrategy
import numpy as np
import pandas as pd


class DragonFirstYinV36(BaseStrategy):
    name = "龙首阴v36"
    description = "龙首阴v36-优化版(自适应涨跌幅+简化过滤+移动止损)"
    custom_id = "C002"

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
        """按板块获取涨停阈值"""
        if board in ("创业板", "科创板"):
            return 0.198  # ±20%
        return 0.098  # 主板/中小板 ±10%

    # 核心参数
    min_limit_ups = 2           # 最少连板数
    max_vol_ratio = 3.0         # 最大量比（相对5日均量）
    atr_ratio_limit = 0.25      # ATR/close 上限（放宽）
    yin_depth_pct = -15.0       # 首阴最深回撤（相对连板起点）
    atr_period = 14
    max_hold_days = 15           # 最长持仓天数
    base_entry_pct = 0.10        # 基础入场仓位
    max_entry_pct = 0.20         # 最大入场仓位

    # 开关：默认关闭过严的过滤
    use_index_filter = False      # 关闭指数过滤（避免 _load_index_data 延迟加载问题）
    use_macd_filter = False       # 关闭MACD过滤（拦截率过高）
    use_kdj_filter = False        # 关闭KDJ过滤（拦截率过高）
    use_confirm_entry = False     # 关闭分批确认（直接入场）
    use_signal_scoring = True     # 信号评分（用于仓位分配）

    # 出场参数（移动止损核心）
    trail_dd_pct = 8.0            # 从最高点回撤8%出场
    trail_atr_mult = 3.0          # 从最高点回落3倍ATR出场
    stop_loss_pct = -10.0         # 硬止损
    take_profit_pct = 25.0        # 止盈阈值（出一半）
    time_stop_days = 15           # 时间止损

    def init(self):
        """初始化指标"""
        close_s = self.data.Close.to_series()
        high_s = self.data.High.to_series()
        low_s = self.data.Low.to_series()
        vol_s = self.data.Volume.to_series()
        open_s = self.data.Open.to_series()
        n = len(close_s)

        # 自动适配涨停阈值
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
            if close_s.iloc[i] / close_s.iloc[i - 1] - 1 >= self._limit_up:
                cnt += 1
            else:
                cnt = 0
            streak_arr[i] = cnt
        self.streak_arr = streak_arr
        self.streak = self.I(lambda: self.streak_arr, name="LimitStreak")

        # 阴线信号
        is_yin_arr = (close_s < open_s).values.astype(bool)
        is_fake_arr = ((close_s > close_s.shift(1)) & (close_s < open_s)).values.astype(bool)
        self.is_yin_arr = is_yin_arr | is_fake_arr
        self.is_yin = self.I(lambda: self.is_yin_arr, name="IsYin")

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

        # K线数组（供持仓管理使用）
        self._s_close = close_s.values
        self._s_high = high_s.values
        self._s_low = low_s.values
        self._s_vol = vol_s.values
        self._s_open = open_s.values

        # 持仓状态
        self._yin_high = None
        self._entry_bar = None
        self._entry_price = 0.0
        self._trail_high = 0.0
        self._add_counts = []

        # 板块检查
        self._board_ok = True
        if self.stock_code:
            board = self.classify_board(self.stock_code)
            self._board_ok = board in self.allowed_boards
            self._cur_board = board

    def _calc_score(self, streak, vol_ratio, yin_depth, atr_ratio):
        """简化版信号评分"""
        s = 0.0
        # 连板强度
        if streak >= 5: s += 30
        elif streak == 4: s += 27
        elif streak == 3: s += 22
        elif streak >= 2: s += 15
        else: s += 5
        # 缩量程度（阴线缩量越好）
        if vol_ratio <= 0.3: s += 20
        elif vol_ratio <= 0.5: s += 17
        elif vol_ratio <= 0.7: s += 14
        elif vol_ratio <= 1.0: s += 10
        elif vol_ratio <= 1.5: s += 6
        elif vol_ratio <= 2.0: s += 3
        # 阴线深度（越浅越好，甚至假阴线）
        if yin_depth >= 0: s += 20
        elif yin_depth >= -2: s += 16
        elif yin_depth >= -4: s += 12
        elif yin_depth >= -6: s += 8
        elif yin_depth >= -8: s += 4
        # ATR比例（波动越小越好）
        if atr_ratio <= 0.03: s += 15
        elif atr_ratio <= 0.06: s += 11
        elif atr_ratio <= 0.09: s += 7
        elif atr_ratio <= 0.12: s += 3
        return min(s, 100.0)

    def next(self):
        if len(self.data) < max(self.atr_period, 30) + 1:
            return
        if not self._board_ok:
            return

        cur_idx = len(self.data) - 1
        close = float(self.data.Close[-1])
        prev_close = float(self.data.Close[-2])
        cur_open = float(self.data.Open[-1])
        cur_high = float(self.data.High[-1])
        volume = float(self.data.Volume[-1])
        atr_val = float(self.atr[-1])
        vol_ma5_val = float(self.vol_ma5[-1])
        streak_prev = int(self.streak[-2])
        streak_cur = int(self.streak[-1])
        is_yin = bool(self.is_yin[-1])

        # ---- 入场条件 ----
        # 条件1: 前一日连板数 >= min_limit_ups
        if streak_prev < self.min_limit_ups:
            pass  # 不满足，检查持仓
        # 条件2: 当日不是涨停（避免追板）
        elif streak_cur >= 1 and close / prev_close - 1 >= self._limit_up:
            pass
        # 条件3: 当日是阴线
        elif not is_yin:
            pass
        # 条件4: 没有持仓、没有待入场信号
        elif self.position:
            pass
        else:
            # ---- 入场检查 ----
            # 非跌停
            not_limit_down = close > prev_close * (1 - self._limit_down - 0.005)
            # 量比
            vol_ratio = volume / vol_ma5_val if vol_ma5_val > 0 else 99
            vol_ok = vol_ma5_val == 0 or volume <= vol_ma5_val * self.max_vol_ratio
            # ATR比例
            atr_ratio = atr_val / close if close > 0 else 1
            atr_ok = atr_val > 0 and atr_ratio < self.atr_ratio_limit
            # 阴线深度（从连板起点算）
            yin_depth = 0
            depth_ok = True
            if streak_prev >= 1 and self.yin_depth_pct < 0:
                limit_close = float(self.data.Close[-(streak_prev + 1)])
                yin_depth = (close - limit_close) / limit_close * 100
                depth_ok = yin_depth >= self.yin_depth_pct

            if not_limit_down and vol_ok and atr_ok and depth_ok and not self.position:
                score = self._calc_score(streak_prev, vol_ratio, yin_depth, atr_ratio)
                # 根据评分动态分配仓位
                if score >= 85:
                    entry_pct = self.max_entry_pct
                elif score >= 70:
                    entry_pct = self.base_entry_pct * 1.5
                elif score >= 55:
                    entry_pct = self.base_entry_pct
                elif score >= 40:
                    entry_pct = self.base_entry_pct * 0.7
                else:
                    entry_pct = self.base_entry_pct * 0.3

                entry_cash = self.equity * entry_pct
                n_shares = int(entry_cash / close / 100) * 100
                if n_shares >= 100:
                    self.buy(size=n_shares)
                    self._entry_price = close
                    self._entry_bar = cur_idx
                    self._yin_high = cur_high
                    self._trail_high = close
                    self._add_counts = []
                    return

        # ---- 持仓管理（移动止损核心） ----
        if self.position and self._entry_bar is not None:
            bars_held = cur_idx - self._entry_bar

            # 更新最高价
            self._trail_high = max(self._trail_high, close)
            profit_pct = (close - self._entry_price) / self._entry_price * 100

            # 1) 止盈: 盈利达目标出一半
            if profit_pct >= self.take_profit_pct and self.position.size > 100:
                half = self.position.size // 2
                self.sell(size=half)
                # 出一半后提高止损线
                self._trail_high = close
                return

            # 2) 跟踪止损: 从最高点回撤一定比例
            if self._trail_high > self._entry_price:
                dd_from_peak = (self._trail_high - close) / self._trail_high * 100
                atr_from_peak = (self._trail_high - close) / atr_val if atr_val > 0 else 999
                if dd_from_peak >= self.trail_dd_pct or atr_from_peak >= self.trail_atr_mult:
                    self.position.close()
                    return

            # 3) 硬止损
            if profit_pct <= self.stop_loss_pct:
                self.position.close()
                return

            # 4) 时间止损
            if bars_held >= self.time_stop_days:
                self.position.close()
                return