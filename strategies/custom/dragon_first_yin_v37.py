# -*- coding: utf-8 -*-
"""龙首阴策略 v37 — 精选版

基于 quant-codex 项目全部经验和教训：

经验来源：
1. 5轮迭代（改1~改5）确认：移动止损是最大突破（科创正占比22.2%→51.9%）
2. v35 发现：MACD/KDJ/Index三过滤拦截率过高（创业板-64%信号），不适合龙首阴
3. _apply_board_params() 覆盖问题已修复（新增 _use_board_params 开关）
4. 前复权数据扭曲历史涨停信号
5. 实战发现：首阴日缩量是质量核心，假阴线（close>prev_close但close<open）最佳

v37 核心改进：
- 入场加质：首阴缩量加分但不强制，放量高分连板也可入场
- 假阴线优先（评分加成）
- 自适应跟踪止损：按ATR动态调整回撤容忍度
- 出场结构紧凑（6%回撤/2.5倍ATR/8%硬止损/12天时间）
"""
from strategies._base import BaseStrategy
import numpy as np


class DragonFirstYinV37(BaseStrategy):
    name = "龙首阴v37"
    description = "龙首阴v37-精选版(缩量确认+假阴线优先+自适应移动止损)"
    custom_id = "C003"

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

    # ---- 入场参数 ----
    min_limit_ups = 2           # 最少连板数
    max_vol_ratio = 2.5         # 首阴日量比上限（适当放宽）
    atr_ratio_limit = 0.25      # ATR/close上限
    yin_depth_pct = -12.0       # 首阴最深回撤
    atr_period = 14
    base_entry_pct = 0.10
    max_entry_pct = 0.25

    # ---- 出场参数（移动止损核心） ----
    trail_dd_pct = 6.0          # 从最高点回撤6%出场
    trail_atr_mult = 2.5        # 回落2.5倍ATR出场
    stop_loss_pct = -8.0        # 硬止损-8%
    take_profit_pct = 20.0      # 盈利20%出一半
    time_stop_days = 12         # 12天时间止损

    # ---- 开关 ----
    use_signal_scoring = True
    prefer_shrink_volume = True  # 缩量加分

    def init(self):
        close_s = self.data.Close.to_series()
        high_s = self.data.High.to_series()
        low_s = self.data.Low.to_series()
        vol_s = self.data.Volume.to_series()
        open_s = self.data.Open.to_series()
        n = len(close_s)

        # 自动涨停阈值
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
            if close_s.iloc[i] / close_s.iloc[i - 1] - 1 >= self._limit_up:
                cnt += 1
            else:
                cnt = 0
            streak_arr[i] = cnt
        self.streak_arr = streak_arr
        self.streak = self.I(lambda: self.streak_arr, name="LimitStreak")

        # 阴线信号（含假阴线）
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

        # K线数据
        self._s_close = close_s.values
        self._s_high = high_s.values
        self._s_low = low_s.values
        self._s_vol = vol_s.values
        self._s_open = open_s.values

        # 状态
        self._entry_bar = None
        self._entry_price = 0.0
        self._trail_high = 0.0

        # 板块检查
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
        else: s += 10
        if vol_ratio <= 0.3: s += 25
        elif vol_ratio <= 0.5: s += 20
        elif vol_ratio <= 0.7: s += 15
        elif vol_ratio <= 1.0: s += 8
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
        if len(self.data) < max(self.atr_period, 30) + 1:
            return
        if not self._board_ok:
            return

        cur_idx = len(self.data) - 1
        close = float(self.data.Close[-1])
        prev_close = float(self.data.Close[-2])
        cur_high = float(self.data.High[-1])
        volume = float(self.data.Volume[-1])
        atr_val = float(self.atr[-1])
        vol_ma5_val = float(self.vol_ma5[-1])
        atr_ratio = atr_val / close if close > 0 else 1
        streak_prev = int(self.streak[-2])
        streak_cur = int(self.streak[-1])
        is_yin = bool(self.is_yin[-1])
        is_fake_yin = bool(self._is_fake_yin_arr[cur_idx]) if cur_idx < len(self._is_fake_yin_arr) else False

        # ---- 入场 ----
        if (streak_prev >= self.min_limit_ups
            and not (streak_cur >= 1 and close / prev_close - 1 >= self._limit_up)
            and is_yin
            and not self.position):

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

            # 自适应跟踪止损
            adaptive_dd = max(self.trail_dd_pct, atr_ratio * 100 * 2)
            adaptive_atr = max(self.trail_atr_mult, 2.0)

            # 1) 止盈
            if profit_pct >= self.take_profit_pct and self.position.size > 100:
                self.sell(size=self.position.size // 2)
                self._trail_high = close
                return

            # 2) 跟踪止损
            if self._trail_high > self._entry_price:
                dd_from_peak = (self._trail_high - close) / self._trail_high * 100
                atr_from_peak = (self._trail_high - close) / atr_val if atr_val > 0 else 999
                if dd_from_peak >= adaptive_dd or atr_from_peak >= adaptive_atr:
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