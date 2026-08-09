# -*- coding: utf-8 -*-
"""全量快速扫描+选择性回测 — v38 全市场验证"""
import os, time, pandas as pd, numpy as np
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
         if f.endswith('.parquet') and not f.startswith('_')
         and f[:3] in ('688','002')])

print(f'Step 1: Fast numpy scan on {len(files)} stocks...')
t0 = time.time()
signals = []
for idx, code in enumerate(files):
    try:
        df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
        col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
        rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
        df = df.rename(columns=rename)
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.set_index('trade_date')
        df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
        if len(df) < 200: continue
    except: continue
    c = df['Close'].values; o = df['Open'].values
    n = len(c)
    limit_up = 0.198 if code.startswith('688') else 0.098
    streak = np.zeros(n); cnt = 0
    for i in range(1, n):
        if c[i]/c[i-1]-1 >= limit_up: cnt += 1
        else: cnt = 0
        streak[i] = cnt
    sig_count = 0
    for i in range(1, n):
        if streak[i-1] >= 2 and c[i] < o[i] and c[i]/c[i-1]-1 < limit_up:
            sig_count += 1
    if sig_count > 0:
        signals.append((code, sig_count, n, '科创板' if code.startswith('688') else '中小板'))
    if (idx+1) % 200 == 0:
        print(f'  Scan: {idx+1}/{len(files)} found={len(signals)} ({time.time()-t0:.0f}s)')

print(f'Scan complete: {len(signals)}/{len(files)} stocks with signals ({time.time()-t0:.0f}s)')
signals.sort(key=lambda x: -x[1])

for board in ['中小板', '科创板']:
    n_board = sum(1 for c in files if c[:3] == ('002' if board == '中小板' else '688'))
    n_sig = sum(1 for s in signals if s[3] == board)
    print(f'  {board}: {n_sig}/{n_board} ({n_sig/n_board*100:.0f}%)')

# 200只完整回测
top_n = min(200, len(signals))
print(f'\nStep 2: Full backtest v38 on top {top_n} signal stocks...')
from backtesting import Backtest
from strategies.custom.dragon_first_yin_v38 import DragonFirstYinV38

t1 = time.time()
all_results = []
for idx in range(top_n):
    code, sig_count, _, board = signals[idx]
    try:
        df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
        col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
        rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
        df = df.rename(columns=rename)
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.set_index('trade_date')
        df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
        df.index.name = 'Date'
        Strat = type('T', (DragonFirstYinV38,), {'stock_code': code})
        bt = Backtest(df, Strat, cash=100000, commission=0.0003)
        r = bt.run()
        if r['# Trades'] > 0:
            all_results.append({
                'code': code, 'board': board, 'signals': sig_count,
                'trades': r['# Trades'], 'ret': r['Return [%]'],
                'sharpe': r.get('Sharpe Ratio', 0), 'dd': r.get('Max. Drawdown [%]', 0),
                'wr': r.get('Win Rate [%]', 0),
            })
    except: pass
    if (idx+1) % 50 == 0 or idx == top_n-1:
        elapsed = time.time() - t1
        print(f'  Backtest: {idx+1}/{top_n} traded={len(all_results)} {elapsed:.0f}s')

elapsed = round(time.time() - t1, 1)
print(f'\nFull backtest complete: {elapsed}s')
print(f'Traded: {len(all_results)}/{top_n}')

for board_label in ['中小板', '科创板']:
    data = [r for r in all_results if r['board'] == board_label]
    if not data: continue
    rets = [r['ret'] for r in data]
    n_with = len(data)
    avg_ret = np.mean(rets)
    med_ret = np.median(rets)
    avg_sh = np.mean([r['sharpe'] for r in data])
    avg_wr = np.mean([r['wr'] for r in data])
    avg_dd = np.mean([r['dd'] for r in data])
    pos_ratio = sum(1 for r in rets if r>0)/n_with*100
    print(f'\n{board_label} ({n_with} stocks):')
    print(f'  avg_ret={avg_ret:+.2f}%  med_ret={med_ret:+.2f}%  pos_ratio={pos_ratio:.0f}%')
    print(f'  avg_sharpe={avg_sh:.3f}  avg_wr={avg_wr:.1f}%  avg_dd={avg_dd:.2f}%')
    top5 = sorted(data, key=lambda r: -r['ret'])[:5]
    top5_str = ', '.join(f"{r['code']}({r['ret']:+.1f}%)" for r in top5)
    print(f'  TOP5: {top5_str}')
    worst5 = sorted(data, key=lambda r: r['ret'])[:5]
    worst5_str = ', '.join(f"{r['code']}({r['ret']:+.1f}%)" for r in worst5)
    print(f'  WORST5: {worst5_str}')

avg_ret_all = np.mean([r['ret'] for r in all_results])
print(f'\n=== FINAL SUMMARY ===')
print(f'Stocks traded: {len(all_results)}')
print(f'Average return: {avg_ret_all:+.2f}%')
wr_all = sum(1 for r in all_results if r['ret']>0)/len(all_results)*100
print(f'Win ratio (stocks): {wr_all:.0f}%')
print('Done')
