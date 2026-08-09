# -*- coding: utf-8 -*-
\"\"\"策略效果报告 — 龙首阴 v41 因子选股版终局验证\"\"\"
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from backtesting import Backtest
from strategies.custom.strategy_004_dragon_first_yin_v38 import DragonFirstYinV38
from strategies.custom.strategy_007_dragon_first_yin_v41 import DragonFirstYinV41

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

CACHE = r'C:\\Users\\Administrator\\Codex-Workspace\\quant-codex\\data\\cache'
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')

codes = ['002432','002164','002211','002178','002400','002456','002229',
         '002529','002855','002553','002418','002667','002951','002181',
         '002725','002943','002316','002512','002272','002348']

strategies = {'v38(最优基准)': DragonFirstYinV38, 'v41(因子选股)': DragonFirstYinV41}
results = {k: [] for k in strategies}

print("Running 20-stock comparison...")
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
    for ver, cls in strategies.items():
        Strat = type('T', (cls,), {'stock_code': code})
        try:
            bt = Backtest(df, Strat, cash=100000, commission=0.0003)
            r = bt.run()
            results[ver].append({'code': code, 'trades': r['# Trades'], 'ret': r['Return [%]'],
                'sharpe': r.get('Sharpe Ratio', 0), 'dd': r.get('Max. Drawdown [%]', 0),
                'wr': r.get('Win Rate [%]', 0), 'pf': r.get('Profit Factor', 0)})
        except Exception as e:
            results[ver].append({'code': code, 'trades': -1, 'ret': 0})
    print(f'  {code} done')

# Summary
print()
print('=' * 65)
print('Ver            有交易  均交易  均收益%   均夏普   均回撤%  正收益比  均胜率')
print('-' * 65)
for ver in ['v38(最优基准)', 'v41(因子选股)']:
    data = [r for r in results[ver] if r['trades'] > 0]
    n_with = len(data)
    if n_with == 0: continue
    avg_t = np.mean([r['trades'] for r in data])
    avg_ret = np.mean([r['ret'] for r in data])
    avg_sh = np.mean([r['sharpe'] for r in data])
    avg_dd = np.mean([r['dd'] for r in data])
    pos_ratio = sum(1 for r in data if r['ret'] > 0)/n_with*100
    avg_wr = np.mean([r['wr'] for r in data]) if data else 0
    print(f'{ver:20s} {n_with:>8}/{len(codes)} {avg_t:>6.1f} {avg_ret:>8.2f} {avg_sh:>8.3f} {avg_dd:>8.2f} {pos_ratio:>8.1f}% {avg_wr:>7.1f}%')

print()
print('Code     v38T v38R    v41T v41R    Best')
print('-' * 42)
for code in codes:
    v38d = next((r for r in results['v38(最优基准)'] if r['code'] == code), None)
    v41d = next((r for r in results['v41(因子选股)'] if r['code'] == code), None)
    if v38d and v41d:
        best = 'v38' if v38d['ret'] >= v41d['ret'] else 'v41'
        print(f'{code:>8} {v38d[\"trades\"]:>4} {v38d[\"ret\"]:>7.2f} {v41d[\"trades\"]:>4} {v41d[\"ret\"]:>7.2f} {best:>6}')

# Save comparison chart
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for idx, (metric, title) in enumerate([('ret', 'Average Return (%)'), ('sharpe', 'Sharpe Ratio')]):
    ax = axes[idx]
    labels = list(strategies.keys())
    vals = [np.mean([r[metric] for r in results[v] if r['trades'] > 0]) for v in labels]
    colors = ['#66b3ff' if v >= 0 else '#ff9999' for v in vals]
    bars = ax.bar(labels, vals, color=colors, width=0.4)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.2 if val >= 0 else -1),
                f'{val:.2f}', ha='center', va='bottom' if val >= 0 else 'top', fontsize=11)
    ax.set_title(title, fontsize=13)
    ax.axhline(0, color='gray', linewidth=0.5)
    ax.grid(axis='y', alpha=0.3)
plt.suptitle('v38 vs v41 Final Comparison (20 stocks)', fontsize=15)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT, 'v38_vs_v41_final.png'), dpi=150, bbox_inches='tight')
plt.close()
print(f'Chart saved to {os.path.join(OUTPUT, \"v38_vs_v41_final.png\")}')
print('Done')