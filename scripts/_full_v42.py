import sys, os, time, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtesting import Backtest
from strategies.custom.dragon_first_yin_v42 import DragonFirstYinV42

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
         if f.endswith('.parquet') and not f.startswith('_')
         and f[:3] in ('688','002')])

# Quick scan to find top signal stocks
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
    limit_up = 0.198 if code.startswith('688') else 0.098
    streak = np.zeros(len(c)); cnt = 0
    for i in range(1, len(c)):
        if c[i]/c[i-1]-1 >= limit_up: cnt += 1
        else: cnt = 0
        streak[i] = cnt
    sig = sum(1 for i in range(1,len(c)) if streak[i-1]>=2 and c[i]<o[i] and c[i]/c[i-1]-1<limit_up)
    if sig > 0: signals.append((code, sig))
signals.sort(key=lambda x: -x[1])
print(f"Scan: {len(signals)} stocks with signals")

# Backtest top 200 with v42
top_n = min(200, len(signals))
results = []
t1 = time.time()
for idx in range(top_n):
    code, sig_cnt = signals[idx]
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
        Strat = type('T', (DragonFirstYinV42,), {'stock_code': code})
        bt = Backtest(df, Strat, cash=100000, commission=0.0003)
        r = bt.run()
        if r['# Trades'] > 0:
            results.append({'code': code, 'trades': r['# Trades'], 'ret': r['Return [%]'],
                'sharpe': r.get('Sharpe Ratio', 0)})
    except: pass
    if (idx+1) % 50 == 0:
        print(f'  {idx+1}/{top_n} traded={len(results)} ({time.time()-t1:.0f}s)')

avg_ret = np.mean([r['ret'] for r in results])
pos_ratio = sum(1 for r in results if r['ret']>0)/len(results)*100
avg_sh = np.mean([r['sharpe'] for r in results])
print(f'\nv42 full backtest (top {top_n}):')
print(f'  Traded: {len(results)}/{top_n}')
print(f'  Avg return: {avg_ret:+.2f}%')
print(f'  Positive ratio: {pos_ratio:.0f}%')
print(f'  Avg sharpe: {avg_sh:.3f}')
print(f'  v38 baseline: -0.04%')
print(f'  v42 vs v38: {avg_ret - (-0.04):+.2f}%')
print('Done')