# -*- coding: utf-8 -*-
"""因子评分模块 - 轻量版"""
import numpy as np
import pandas as pd


def compute_dragon_factors(close, high, low, open_, volume):
    """计算精选因子，返回 dict of arrays"""
    n = len(close)
    if n < 30:
        return {}
    
    close_s = pd.Series(close)
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    open_s = pd.Series(open_)
    vol_s = pd.Series(volume)

    ret = close_s.pct_change()
    vol_chg = vol_s.pct_change()

    # alpha001: 量价方向一致性
    alpha001 = -1 * (vol_chg.rolling(6).rank() * (ret / close_s.shift(1)).rolling(6).rank()).rolling(6).corr(close_s.rank())

    # alpha011: 日内多空强度×量
    range_ = high_s - low_s
    intraday_strength = ((close_s - low_s) - (high_s - close_s)) / range_.replace(0, np.nan)
    alpha011 = intraday_strength * vol_s

    # alpha014: 5日涨幅
    alpha014 = close_s.pct_change(5)

    # alpha020: 6日涨幅%
    alpha020 = close_s.pct_change(6) * 100

    # alpha056: 12日位置
    low12 = low_s.rolling(12).min()
    high12 = high_s.rolling(12).max()
    denom = (high12 - low12).replace(0, np.nan)
    alpha056 = (close_s - low12) / denom

    # alpha095: 20日位置
    low20 = low_s.rolling(20).min()
    high20 = high_s.rolling(20).max()
    denom20 = (high20 - low20).replace(0, np.nan)
    alpha095 = (close_s - low20) / denom20

    # alpha015: 开盘强度
    alpha015 = open_s / close_s.shift(1) - 1

    # alpha129简化: 上涨量/下跌量
    up_vol = vol_s.where(ret > 0, 0).rolling(10).sum()
    down_vol = vol_s.where(ret <= 0, 0).rolling(10).sum()
    alpha129 = up_vol / down_vol.replace(0, np.nan)

    # alpha151: 均线偏离
    ma12 = close_s.rolling(12).mean()
    alpha151 = (close_s - ma12) / ma12.replace(0, np.nan)

    # 量比
    streak_vol_ratio = vol_s / vol_s.rolling(20).mean()

    return {
        'alpha001': alpha001.values,
        'alpha011': alpha011.values,
        'alpha014': alpha014.values,
        'alpha020': alpha020.values,
        'alpha056': alpha056.values,
        'alpha095': alpha095.values,
        'alpha015': alpha015.values,
        'alpha129': alpha129.values,
        'alpha151': alpha151.values,
        'streak_vol_ratio': streak_vol_ratio.values,
    }


def calc_signal_score(factors, idx, streak_prev, vol_ratio, yin_depth, atr_ratio, is_fake):
    """根据因子值和信号特征计算综合评分 (0-100)"""
    if idx >= len(factors.get('alpha001', [])):
        return 50

    score = 0.0

    # 连板强度
    if streak_prev >= 5: score += 25
    elif streak_prev == 4: score += 22
    elif streak_prev >= 3: score += 18
    else: score += 12

    # 缩量 (核心指标)
    if vol_ratio <= 0.3: score += 25
    elif vol_ratio <= 0.5: score += 20
    elif vol_ratio <= 0.7: score += 15
    elif vol_ratio <= 1.0: score += 10

    # 假阴线加分
    if is_fake: score += 15

    # 阴线深度
    if yin_depth >= 0: score += 15
    elif yin_depth >= -2: score += 12
    elif yin_depth >= -4: score += 8
    elif yin_depth >= -6: score += 4

    # alpha056: 12日位置
    a56 = factors['alpha056'][idx]
    if not np.isnan(a56):
        if a56 >= 0.8: score += 10
        elif a56 >= 0.6: score += 7
        elif a56 >= 0.4: score += 4

    # alpha095: 20日位置
    a95 = factors['alpha095'][idx]
    if not np.isnan(a95):
        if a95 >= 0.7: score += 8
        elif a95 >= 0.5: score += 5

    # alpha151: 均线偏离
    a151 = factors['alpha151'][idx]
    if not np.isnan(a151):
        if a151 > 0.05: score += 7
        elif a151 > 0: score += 4

    # alpha015: 开盘强度
    a15 = factors['alpha015'][idx]
    if not np.isnan(a15):
        if a15 < -0.02: score += 5
        elif a15 > 0.02: score -= 3

    # ATR比例
    if atr_ratio <= 0.05: score += 8
    elif atr_ratio <= 0.10: score += 5
    elif atr_ratio <= 0.15: score += 2

    return min(100, max(0, score))