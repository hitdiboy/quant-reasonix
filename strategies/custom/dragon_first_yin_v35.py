# -*- coding: utf-8 -*-
"""龙首阴策略 v35 — 板块轮动+MACD/KDJ确认+动态加仓"""

from strategies._base import BaseStrategy
import numpy as np
import pandas as pd


class DragonFirstYin(BaseStrategy):
    name = "龙首阴"
    description = "龙首阴v35-板块轮动+MACD/KDJ+动态加仓"
    custom_id = "C001"

    stock_code = ""
    allowed_boards = ["创业板","中小板","科创板"]

    @staticmethod
    def classify_board(code):
        if code.startswith("688"): return "科创板"
        if code.startswith("300"): return "创业板"
        if code.startswith("002"): return "中小板"
        return "其他"

    min_limit_ups = 2
    max_vol_ratio = 3.0
    limit_up_threshold = 0.098
    only_fake_yin = False
    atr_ratio_limit = 0.18
    yin_depth_pct = -12.0
    atr_period = 14
    entry_pct = 0.10
    max_hold_days = 20
    use_market_filter = False
    use_confirm_entry = True
    confirm_days = 2
    add_window_days = 5
    add_split_batches = 2
    real_yin_wait_days = 0
    use_signal_scoring = True
    base_entry_pct = 0.10
    max_entry_pct = 0.20
    limit_down_threshold = 0.098
    use_index_filter = True
    _index_cache = {}
    _use_board_params = True  # False 则跳过 _apply_board_params()
    
    # MACD/KDJ 开关
    use_macd_filter = True
    use_kdj_filter = True

    BOARD_PARAMS = {
        "创业板": {
            "min_limit_ups": 2, "limit_up_threshold": 0.098, "max_vol_ratio": 2.0,
            "atr_ratio_limit": 0.18, "yin_depth_pct": -12.0,
            "base_entry_pct": 0.10, "max_entry_pct": 0.20,
            "limit_down_threshold": 0.198, "index_code": "399006",
        },
        "中小板": {
            "min_limit_ups": 2, "limit_up_threshold": 0.098, "max_vol_ratio": 1.5,
            "atr_ratio_limit": 0.15, "yin_depth_pct": -8.0,
            "base_entry_pct": 0.08, "max_entry_pct": 0.15,
            "limit_down_threshold": 0.098, "index_code": "399005",
        },
        "科创板": {
            "min_limit_ups": 1, "limit_up_threshold": 0.198, "max_vol_ratio": 2.5,
            "atr_ratio_limit": 0.20, "yin_depth_pct": -15.0,
            "base_entry_pct": 0.12, "max_entry_pct": 0.25,
            "limit_down_threshold": 0.198, "index_code": "000688",
        },
    }

    def _apply_board_params(self):
        if not self.stock_code or not self._use_board_params:
            return
        board = self.classify_board(self.stock_code)
        params = self.BOARD_PARAMS.get(board)
        if params:
            for k, v in params.items():
                setattr(self, k, v)

    def _calc_signal_score(self, streak, vol_ratio, yin_depth, atr_ratio, market_ok, macd_ok, kdj_ok):
        s = 0.0
        if streak >= 5: s += 30
        elif streak == 4: s += 27
        elif streak == 3: s += 22
        elif streak >= 2: s += 15
        else: s += 5
        if vol_ratio <= 0.3: s += 20
        elif vol_ratio <= 0.5: s += 17
        elif vol_ratio <= 0.7: s += 14
        elif vol_ratio <= 1.0: s += 10
        elif vol_ratio <= 1.5: s += 6
        elif vol_ratio <= 2.0: s += 3
        if yin_depth >= 0: s += 20
        elif yin_depth >= -2: s += 16
        elif yin_depth >= -4: s += 12
        elif yin_depth >= -6: s += 8
        elif yin_depth >= -8: s += 4
        if atr_ratio <= 0.03: s += 15
        elif atr_ratio <= 0.06: s += 11
        elif atr_ratio <= 0.09: s += 7
        elif atr_ratio <= 0.12: s += 3
        if market_ok: s += 15
        if macd_ok: s += 10
        if kdj_ok: s += 10
        return min(s, 100.0)

    def _load_index_data(self, code):
        if code in DragonFirstYin._index_cache:
            return DragonFirstYin._index_cache[code]
        try:
            from data.fetch.unified import fetch
            df = fetch(code)
            if df is not None and len(df) > 50:
                close = df["Close"].values.astype(float)
                ma20 = pd.Series(close).rolling(20).mean().values
                ma5 = pd.Series(close).rolling(5).mean().values
                # MACD
                ema12 = pd.Series(close).ewm(span=12).mean().values
                ema26 = pd.Series(close).ewm(span=26).mean().values
                dif = ema12 - ema26
                dea = pd.Series(dif).ewm(span=9).mean().values
                macd_hist = (dif - dea) * 2
                DragonFirstYin._index_cache[code] = {
                    "close": close, "ma20": ma20, "ma5": ma5,
                    "dates": df.index.values,
                    "dif": dif, "dea": dea, "macd": macd_hist,
                }
                return DragonFirstYin._index_cache[code]
        except:
            pass
        DragonFirstYin._index_cache[code] = None
        return None

    def _check_index_filter(self, cur_idx, board):
        code = self.BOARD_PARAMS.get(board, {}).get("index_code", "399006")
        idx_data = self._load_index_data(str(code))
        if idx_data is None:
            return True
        dates = idx_data["dates"]
        cl = idx_data["close"]
        ma5 = idx_data["ma5"]
        ma20 = idx_data["ma20"]
        idx = int(np.searchsorted(dates, cur_idx, side="right") - 1)
        if idx < 20 or idx >= len(cl):
            return True
        # 增强条件: 收盘 > MA20(多头) AND MA5 > MA20(上升趋势)
        return cl[idx] > ma20[idx] and ma5[idx] > ma20[idx]

    def _calc_macd_kdj(self, close_s, high_s, low_s):
        n = len(close_s)
        # MACD
        ema12 = close_s.ewm(span=12).mean()
        ema26 = close_s.ewm(span=26).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9).mean()
        macd_hist = (dif - dea) * 2

        self._dif_arr = dif.values
        self._dea_arr = dea.values
        self._macd_arr = macd_hist.values
        self.dif = self.I(lambda: self._dif_arr, name="DIF")
        self.dea = self.I(lambda: self._dea_arr, name="DEA")
        self.macd = self.I(lambda: self._macd_arr, name="MACD")

        # KDJ
        low9 = low_s.rolling(9).min()
        high9 = high_s.rolling(9).max()
        rsv = (close_s - low9) / (high9 - low9) * 100
        k_arr = np.zeros(n)
        d_arr = np.zeros(n)
        j_arr = np.zeros(n)
        for i in range(n):
            if i == 0:
                k_arr[i] = 50
                d_arr[i] = 50
            else:
                k_arr[i] = rsv.iloc[i] * 1/3 + k_arr[i-1] * 2/3 if not np.isnan(rsv.iloc[i]) else k_arr[i-1]
                d_arr[i] = k_arr[i] * 1/3 + d_arr[i-1] * 2/3
            j_arr[i] = 3 * k_arr[i] - 2 * d_arr[i]
        self._k_arr = k_arr
        self._d_arr = d_arr
        self._j_arr = j_arr
        self.k_val = self.I(lambda: self._k_arr, name="K")
        self.d_val = self.I(lambda: self._d_arr, name="D")
        self.j_val = self.I(lambda: self._j_arr, name="J")

    def init(self):
        self._apply_board_params()
        close_s = self.data.Close.to_series()
        high_s = self.data.High.to_series()
        low_s = self.data.Low.to_series()
        vol_s = self.data.Volume.to_series()
        open_s = self.data.Open.to_series()
        n = len(close_s)

        # 涨停连续计数
        streak_arr = np.zeros(n)
        cnt = 0
        for i in range(1, n):
            if close_s.iloc[i] / close_s.iloc[i-1] - 1 >= self.limit_up_threshold:
                cnt += 1
            else:
                cnt = 0
            streak_arr[i] = cnt
        self.streak_arr = streak_arr
        self.streak = self.I(lambda: self.streak_arr, name="LimitStreak")

        is_yin_arr = (close_s < open_s).values.astype(bool)
        is_fake_arr = ((close_s > close_s.shift(1)) & (close_s < open_s)).values.astype(bool)
        if self.only_fake_yin:
            self.is_yin_arr = is_fake_arr
        else:
            self.is_yin_arr = is_yin_arr | is_fake_arr
        self.is_yin = self.I(lambda: self.is_yin_arr, name="IsYin")

        tr = np.maximum(high_s - low_s,
            np.maximum(abs(high_s - close_s.shift(1)), abs(low_s - close_s.shift(1))))
        tr.iloc[0] = 0
        self.atr_arr = tr.rolling(self.atr_period).mean().values
        self.atr = self.I(lambda: self.atr_arr, name="ATR")

        self.vol_ma5_arr = vol_s.rolling(5).mean().values
        self.vol_ma5 = self.I(lambda: self.vol_ma5_arr, name="VolMA5")

        # MACD/KDJ
        self._calc_macd_kdj(close_s, high_s, low_s)

        self._s_close = close_s.values
        self._s_high = high_s.values
        self._s_low = low_s.values
        self._s_vol = vol_s.values
        self._s_open = open_s.values

        self._yin_high = None
        self._entry_bar = None
        self._add_counts = []
        self._pending_entry = None
        self._trail_high = 0.0
        self._entry_price = 0.0
        self._signal_idx = 0
        self._board_ok = True
        if self.stock_code:
            board = self.classify_board(self.stock_code)
            self._board_ok = board in self.allowed_boards
            self._cur_board = board

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
        is_yin = bool(self.is_yin[-1])
        is_limit = (close / prev_close - 1) >= self.limit_up_threshold

        not_limit_down = close > prev_close * (1 - self.limit_down_threshold - 0.005)
        vol_ratio = volume / vol_ma5_val if vol_ma5_val > 0 else 99
        vol_ok = vol_ma5_val == 0 or volume <= vol_ma5_val * self.max_vol_ratio
        atr_ratio = atr_val / close if close > 0 else 1
        atr_ok = atr_val > 0 and atr_ratio < self.atr_ratio_limit

        yin_depth = 0
        depth_ok = True
        if streak_prev >= 1 and self.yin_depth_pct < 0:
            limit_close = float(self.data.Close[-(streak_prev + 1)])
            yin_depth = (close - limit_close) / limit_close * 100
            depth_ok = yin_depth >= self.yin_depth_pct

        basic_ok = not_limit_down and vol_ok and atr_ok and depth_ok

        # 板块轮动过滤增强
        market_ok = True
        if basic_ok and self.use_index_filter and hasattr(self, "_cur_board"):
            market_ok = self._check_index_filter(self.data.index[cur_idx], self._cur_board)

        # MACD 过滤
        macd_ok = True
        if basic_ok and self.use_macd_filter and cur_idx >= 33:
            dif_v = float(self.dif[-1])
            dea_v = float(self.dea[-1])
            macd_v = float(self.macd[-1])
            macd_ok = dif_v > dea_v and macd_v > 0

        # KDJ 过滤
        kdj_ok = True
        if basic_ok and self.use_kdj_filter and cur_idx >= 9:
            k_v = float(self.k_val[-1])
            d_v = float(self.d_val[-1])
            kdj_ok = k_v > d_v and k_v > 20

        if self.use_signal_scoring:
            score = self._calc_signal_score(streak_prev, vol_ratio, yin_depth, atr_ratio, market_ok, macd_ok, kdj_ok)
            if score >= 85: dynamic_pct = self.max_entry_pct
            elif score >= 70: dynamic_pct = self.base_entry_pct * 1.5
            elif score >= 55: dynamic_pct = self.base_entry_pct
            elif score >= 40: dynamic_pct = self.base_entry_pct * 0.7
            else: dynamic_pct = self.base_entry_pct * 0.3
        else:
            dynamic_pct = self.entry_pct

        # 分批确认入场
        if self.use_confirm_entry:
            if (streak_prev >= self.min_limit_ups and not is_limit and
                is_yin and basic_ok and market_ok and macd_ok and kdj_ok and
                not self.position and self._pending_entry is None):
                self._pending_entry = {
                    "pct": dynamic_pct,
                    "close": close,
                    "half_pct": dynamic_pct * 0.5,
                    "stage": 0,
                    "signal_vol": volume,
                    "score": score,
                }
                self._signal_idx = cur_idx
                return

            if self._pending_entry is not None and not self.position:
                pe = self._pending_entry
                days_since = cur_idx - self._signal_idx

                if days_since > self.confirm_days:
                    self._pending_entry = None
                    return

                sig_close = pe["close"]
                sig_vol = pe["signal_vol"]
                decline = (close - sig_close) / sig_close * 100
                vol_vs_signal = volume / sig_vol if sig_vol > 0 else 99

                day1_ok = (vol_vs_signal <= 1.2 and decline >= -5.0)
                day2_ok = True
                if days_since == 2:
                    day1_vol = float(self.data.Volume[-2])
                    vol_trend = volume / day1_vol if day1_vol > 0 else 99
                    day2_ok = (vol_trend <= 1.1 and decline >= -5.0)

                if days_since == 1 and day1_ok:
                    score = pe.get("score", 50)
                    if score >= 85: first_ratio = 0.6
                    elif score >= 70: first_ratio = 0.5
                    else: first_ratio = 0.4
                    first_cash = self.equity * pe["pct"] * first_ratio
                    n1 = int(first_cash / close / 100) * 100
                    if n1 >= 100:
                        self.buy(size=n1)
                        self._entry_price = close
                        self._entry_bar = cur_idx
                        self._yin_high = cur_high
                        pe["stage"] = 1
                        pe["first_entry_price"] = close
                        pe["first_entry_size"] = n1
                        return

                if days_since == 2 and day1_ok and day2_ok and pe.get("stage") == 1:
                    rem_ratio = 1.0 - (0.6 if pe.get("score", 50) >= 85 else (0.5 if pe.get("score", 50) >= 70 else 0.4))
                    rem_cash = self.equity * pe["pct"] * rem_ratio
                    n2 = int(rem_cash / close / 100) * 100
                    if n2 >= 100:
                        self.buy(size=n2)
                        old_cost = pe["first_entry_price"] * pe["first_entry_size"]
                        self._entry_price = (old_cost + close * n2) / (pe["first_entry_size"] + n2)
                        self._yin_high = max(self._yin_high or 0, cur_high)
                        self._pending_entry = None
                        return
        else:
            if (streak_prev >= self.min_limit_ups and not is_limit and
                is_yin and basic_ok and market_ok and macd_ok and kdj_ok and not self.position):
                entry_cash = self.equity * dynamic_pct
                n_shares = int(entry_cash / close / 100) * 100
                if n_shares >= 100:
                    self.buy(size=n_shares)
                    self._entry_price = close
                    self._yin_high = cur_high
                    self._entry_bar = cur_idx
                    self._add_counts = []
                    return

        # 持仓管理
        if self.position:
            if self._yin_high is not None and self._entry_bar is not None:
                bars_since = cur_idx - self._entry_bar
                if (bars_since <= self.add_window_days and
                    close > self.vol_ma5_arr[self._entry_bar] * 1.02 and
                    len(self._add_counts) < self.add_split_batches):
                    score = self._calc_signal_score(streak_prev, vol_ratio, yin_depth, atr_ratio, market_ok, macd_ok, kdj_ok)
                    add_ratio = 0.20 if score >= 70 else (0.15 if score >= 50 else 0.08)
                    add_cash = self.equity * add_ratio
                    add_shares = int(add_cash / close / 100) * 100
                    if add_shares >= 100:
                        self.buy(size=add_shares)
                        old_cost = self._entry_price * (self.position.size - add_shares)
                        self._entry_price = (old_cost + close * add_shares) / self.position.size
                        self._yin_high = cur_high
                        self._add_counts.append(1)

            if self._entry_bar is not None:
                bars_held = cur_idx - self._entry_bar
                self._trail_high = max(self._trail_high, close)
                profit_pct = (close - self._entry_price) / self._entry_price * 100

                if profit_pct >= 20.0 and self.position.size > 100:
                    half = self.position.size // 2
                    self.sell(size=half)
                    if profit_pct >= 40.0:
                        self.position.close()
                        return

                if profit_pct >= 15.0:
                    if close <= self._entry_price * 1.002:
                        self.position.close()
                        return

                if profit_pct <= -15.0:
                    self.position.close()
                    return

                if self._trail_high > 0:
                    drawdown = (self._trail_high - close) / self._trail_high * 100
                    atr_drawdown = (self._trail_high - close) / atr_val if atr_val > 0 else 99
                    if drawdown >= 12.0 or atr_drawdown >= 5.0:
                        self.position.close()
                        return

                if bars_held >= self.max_hold_days:
                    self.position.close()
                    return