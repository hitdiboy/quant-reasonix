# -*- coding: utf-8 -*-
"""Test end_of_day breakout strategy"""
import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtesting import Backtest
from strategies.custom.end_of_day_breakout import EndOfDayBreakout

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
codes = ['002432','002456','300059','002164','002400','002553','002855','002529']

results = []
for code in codes:
    df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
    col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
    rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
    df = df.rename(columns=rename)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.set_index('trade_date')
    df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
    df.index.name = 'Date'
    if len(df) < 200: continue

    Strat = type('T', (EndOfDayBreakout,), {'stock_code': code})
    bt = Backtest(df, Strat, cash=100000, commission=0.0003)
    r = bt.run()
    results.append({'code': code, 'trades': r['# Trades'], 'ret': r['Return [%]'],
        'sharpe': r.get('Sharpe Ratio', 0), 'dd': r.get('Max. Drawdown [%]', 0),
        'wr': r.get('Win Rate [%]', 0)})
    print(f'{code}: T={r["# Trades"]} R={r["Return [%]"]:.2f}% WR={r.get("Win Rate [%]",0):.1f}%')

avg_ret = np.mean([r['ret'] for r in results if r['trades']>0])
avg_wr = np.mean([r['wr'] for r in results if r['trades']>0])
avg_sh = np.mean([r['sharpe'] for r in results if r['trades']>0])
pos = sum(1 for r in results if r['ret']>0)
print(f'\n结果: 标的={len(results)} 有交易={sum(1 for r in results if r["trades"]>0)}')
print(f'均收益={avg_ret:.2f}% 正收益比={pos}/{len(results)}({pos*100//len(results)}%)')
print(f'均胜率={avg_wr:.1f}% 均夏普={avg_sh:.3f}')