# -*- coding: utf-8 -*-
"""龙首阴策略 v42 — ML驱动版

基于 ML 模型在 3330 个信号上的训练结果（核心系数）：
  streak:  -0.246  ← 连板越多越差！2-3板最优
  is_fake: +0.196  ← 假阴线是最强正向信号
  atr_ratio: +0.172 ← 高波动反而更好（活股才有第二波）
  yin_depth: +0.022 ← 阴线稍深反而好（恐慌出清充分）

v42 关键改进：
1. 偏好 2-3 连板而非更高连板（反转效应）
2. 假阴线大幅加分，真阴线扣分
3. 低波动标的过滤（ATR ratio 低=死股=不做）
4. 仓位按 ML 评分梯度分配
"""
from strategies._base import BaseStrategy
import numpy as np
import pandas as pd


class DragonFirstYinV42(BaseStrategy):
    name = "龙首阴v42"
    description = "龙首阴v42-ML驱动版(连板反转+假阴线优先+波动过滤)"
    custom_id = "C008"

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

    # --- 入场参数（ML优化版）---
    min_fake_yin_bonus = 3       # 假阴线直接+3分
    max_streak_preferred = 3     # 偏好不超过3连板
    min_atr_ratio = 0.04        # ATR/close > 4%（过滤死股）
    max_vol_ratio = 2.5
    atr_ratio_limit = 0.28
    yin_depth_pct = -12.0
    atr_period = 14
    base_entry_pct = 0.10
    max_entry_pct = 0.25

    # --- 出场参数 ---
    trail_dd_pct = 8.0
    trail_atr_mult = 3.0
    stop_loss_pct = -12.0
    take_profit_pct = 25.0
    time_stop_days = 15
    grace_period_days = 3

    # 用 ML 模型做最终过滤
    use_ml_filter = True

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
        streak_arr = np.zeros(n); cnt = 0
        for i in range(1, n):
            if close_s.iloc[i] / close_s.iloc[i-1] - 1 >= self._limit_up:
                cnt += 1
            else: cnt = 0
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

        # MA20偏离
        self.ma20_arr = close_s.rolling(20).mean().values
        self.ma20 = self.I(lambda: self.ma20_arr, name="MA20")

        # 尝试加载ML模型
        self._ml_model = None
        self._ml_features = None
        try:
            import pickle, os
            _p = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'ml_selector.pkl')
            if os.path.exists(_p):
                data = pickle.load(open(_p, 'rb'))
                if isinstance(data, dict):
                    self._ml_model = data.get('model')
                    self._ml_features = data.get('features')
        except: pass

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

    def _calc_ml_score(self, cur_idx, streak, vol_r, depth, atr_r, is_fk, ma20_d, ret20, price):
        """ML 预测评分 0-100"""
        if self._ml_model is None or cur_idx < 20:
            return None
        try:
            import pandas as pd
            feat = np.array([[streak, vol_r, depth, atr_r, int(is_fk), ma20_d, ret20, price]])
            feat_df = pd.DataFrame(feat, columns=self._ml_features).fillna(0)
            proba = self._ml_model.predict_proba(feat_df)[0, 1]
            return int(proba * 100)
        except: return None

    def _calc_score(self, streak, vol_ratio, yin_depth, atr_ratio, is_fake, ma20_dev):
        """ML驱动的评分函数"""
        s = 0.0
        # 连板评分：2-3板最佳（ML模型显示streak系数为负）
        if streak == 2: s += 25       # 最优
        elif streak == 3: s += 22     # 次优
        elif streak == 4: s += 12     # 衰减
        elif streak >= 5: s += 5      # 反转风险
        else: s += 10

        # 假阴线（最强正向信号 ML系数+0.196）
        if is_fake: s += 25
        else: s += 5  # 真阴线减分

        # 波动率（ATR系数+0.172，高波动活股）
        if atr_ratio >= 0.08: s += 15
        elif atr_ratio >= 0.05: s += 10
        elif atr_ratio >= 0.03: s += 5

        # 缩量加分
        if vol_ratio <= 0.3: s += 15
        elif vol_ratio <= 0.5: s += 12
        elif vol_ratio <= 0.7: s += 8
        elif vol_ratio <= 1.0: s += 4

        # 阴线深度（系数+0.022，稍深反而好）
        if yin_depth >= 0: s += 10
        elif yin_depth >= -3: s += 8
        elif yin_depth >= -6: s += 5
        elif yin_depth >= -10: s += 2

        # MA20偏离（系数-0.027，避免太高位置）
        if ma20_dev < 15: s += 5
        elif ma20_dev < 30: s += 2
        else: s -= 3

        return min(100, max(0, s))

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
        ma20_val = float(self.ma20[-1])
        ma20_dev = (close - ma20_val) / ma20_val * 100 if ma20_val > 0 else 0
        streak_prev = int(self.streak[-2])
        streak_cur = int(self.streak[-1])
        is_yin = bool(self.is_yin[-1])
        is_fake_yin = bool(self._is_fake_yin_arr[cur_idx]) if cur_idx < len(self._is_fake_yin_arr) else False

        # 计算20日涨幅（用于ML特征）
        ret_20d = (close - float(self.data.Close[-21])) / float(self.data.Close[-21]) * 100 if len(self.data) > 21 else 0

        # ---- 入场 ----
        if (streak_prev >= 2
            and not (streak_cur >= 1 and close / prev_close - 1 >= self._limit_up)
            and is_yin
            and not self.position):

            not_limit_down = close > prev_close * (1 - self._limit_down - 0.005)
            vol_ratio = volume / vol_ma5_val if vol_ma5_val > 0 else 99
            vol_ok = volume <= vol_ma5_val * self.max_vol_ratio if vol_ma5_val > 0 else True
            atr_ok = atr_val > 0 and atr_ratio < self.atr_ratio_limit and atr_ratio >= self.min_atr_ratio

            yin_depth = 0; depth_ok = True
            if streak_prev >= 1:
                limit_close = float(self.data.Close[-(streak_prev + 1)])
                yin_depth = (close - limit_close) / limit_close * 100
                depth_ok = yin_depth >= self.yin_depth_pct

            if not_limit_down and vol_ok and atr_ok and depth_ok:
                # ML评分
                ml_score = self._calc_ml_score(cur_idx, streak_prev, vol_ratio, yin_depth,
                                               atr_ratio, is_fake_yin, ma20_dev, ret_20d, close)
                if ml_score is not None:
                    final_score = ml_score
                else:
                    final_score = self._calc_score(streak_prev, vol_ratio, yin_depth,
                                                   atr_ratio, is_fake_yin, ma20_dev)

                if final_score >= 50:
                    if final_score >= 80: entry_pct = self.max_entry_pct
                    elif final_score >= 65: entry_pct = self.base_entry_pct * 1.5
                    elif final_score >= 50: entry_pct = self.base_entry_pct
                    else: entry_pct = self.base_entry_pct * 0.5

                    n_shares = int(self.equity * entry_pct / close / 100) * 100
                    if n_shares >= 100:
                        self.buy(size=n_shares)
                        self._entry_price = close
                        self._entry_bar = cur_idx
                        self._trail_high = close
                        return

        # ---- 持仓管理（同v38最优）----
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