# -*- coding: utf-8 -*-
"""市场状态识别器"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd, numpy as np

def detect_market_state():
    """识别当前市场状态"""
    score = 50
    try:
        from data.fetch.unified import fetch
        df = fetch('159915', start='20240601')
        if df is not None and len(df) > 20:
            c = df['Close'].values
            ma20 = pd.Series(c).rolling(20).mean().values
            ma60 = pd.Series(c).rolling(60).mean().values
            latest = c[-1]
            ma20_val = ma20[-1]; ma60_val = ma60[-1] if not np.isnan(ma60[-1]) else latest
            if latest > ma20_val: score += 15
            if latest > ma60_val: score += 10
            ret_5d = (c[-1] - c[-6]) / c[-6] * 100 if len(c) >= 6 else 0
            if ret_5d > 3: score += 15
            elif ret_5d > 1: score += 8
            elif ret_5d < -3: score -= 15
            elif ret_5d < -1: score -= 8
            daily_ret = np.diff(c[-30:]) / c[-30:-1] if len(c) >= 30 else np.diff(c) / c[:-1]
            vol = np.std(daily_ret) * 100
            if vol > 2.5: score += 10
            elif vol < 1.0: score -= 10
            open_ = df['Open'].values
            if c[-1] > open_[-1]: score += 5
    except:
        pass
    score = max(0, min(100, score))
    if score >= 65: state, preferred = "趋势行情", "动量突破"
    elif score >= 40: state, preferred = "震荡行情", "龙首阴"
    else: state, preferred = "回调行情", "保守/龙首阴"
    return {'score': score, 'state': state, 'preferred': preferred}

if __name__ == '__main__':
    r = detect_market_state()
    print(f"市场状态: {r['score']}/100 - {r['state']}")
    print(f"推荐策略: {r['preferred']}")
