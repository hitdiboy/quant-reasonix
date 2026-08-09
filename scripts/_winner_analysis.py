# -*- coding: utf-8 -*-
"""赢家 vs 输家特征分析"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
codes_winners = ['002565','002374','002178','002647','002551']
codes_losers = ['002717','002800','002403','002172','002670']

def analyze(code):
    df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
    col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
    rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
    df = df.rename(columns=rename)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.set_index('trade_date')
    df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
    c = df['Close'].values; o = df['Open'].values; v = df['Volume'].values
    n = len(c)
    limit_up = 0.198 if code.startswith('688') else 0.098
    streak = np.zeros(n); cnt = 0
    for i in range(1, n):
        if c[i]/c[i-1]-1 >= limit_up: cnt += 1
        else: cnt = 0
        streak[i] = cnt
    sig_count = 0
    fwd_returns = []
    for i in range(1, n - 5):
        if streak[i-1] >= 2 and c[i] < o[i] and c[i]/c[i-1]-1 < limit_up:
            sig_count += 1
            fwd_ret = (c[i+5] - c[i]) / c[i] * 100
            fwd_returns.append(fwd_ret)
    avg_fwd = np.mean(fwd_returns) if fwd_returns else 0
    pos_fwd = sum(1 for r in fwd_returns if r > 0) / len(fwd_returns) * 100 if fwd_returns else 0
    daily_ret = np.diff(c) / c[:-1]
    annual_vol = np.std(daily_ret) * np.sqrt(252) * 100
    return {'code': code, 'sig_count': sig_count, 'avg_fwd_5d': avg_fwd, 'pos_fwd_5d': pos_fwd, 'annual_vol': annual_vol}

print('Code     SigCnt  AvgFwd5d%  PosFwd5d%  AnnVol%')
print('-' * 50)
print('\n--- WINNERS ---')
for code in codes_winners:
    f = analyze(code)
    print(f'{code:>8} {f["sig_count"]:>6} {f["avg_fwd_5d"]:>9.2f} {f["pos_fwd_5d"]:>9.0f} {f["annual_vol"]:>8.1f}')
print('\n--- LOSERS ---')
for code in codes_losers:
    f = analyze(code)
    print(f'{code:>8} {f["sig_count"]:>6} {f["avg_fwd_5d"]:>9.2f} {f["pos_fwd_5d"]:>9.0f} {f["annual_vol"]:>8.1f}')
print('\nDone')