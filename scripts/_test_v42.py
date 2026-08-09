import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np
from backtesting import Backtest
from strategies.custom.dragon_first_yin_v38 import DragonFirstYinV38
from strategies.custom.dragon_first_yin_v42 import DragonFirstYinV42

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
codes = ['002432','002164','002211','002178','002400','002456','002229',
         '002529','002855','002553','002418','002667','002951','002181',
         '002725','002943','002316','002512','002272','002348']
strategies = {'v38': DragonFirstYinV38, 'v42(ML)': DragonFirstYinV42}
results = {k: [] for k in strategies}
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
                'sharpe': r.get('Sharpe Ratio', 0), 'dd': r.get('Max. Drawdown [%]', 0)})
        except: results[ver].append({'code': code, 'trades': 0, 'ret': 0})

print('Ver     Traded  AvgT  AvgRet%  AvgShp  AvgDD%  PosRatio')
print('-' * 55)
for ver in ['v38','v42(ML)']:
    data = [r for r in results[ver] if r['trades'] > 0]
    n_with = len(data)
    if n_with == 0: continue
    avg_t = np.mean([r['trades'] for r in data])
    avg_ret = np.mean([r['ret'] for r in data])
    avg_sh = np.mean([r['sharpe'] for r in data])
    avg_dd = np.mean([r['dd'] for r in data])
    pos_ratio = sum(1 for r in data if r['ret'] > 0)/n_with*100
    print(f'{ver:>10} {n_with:>4}/{len(codes)} {avg_t:>5.1f} {avg_ret:>8.2f} {avg_sh:>8.3f} {avg_dd:>8.2f} {pos_ratio:>8.1f}%')
print()
print('Code     v38T  v38R    v42T v42R    Best')
print('-' * 40)
for code in codes:
    v38d = next((r for r in results['v38'] if r['code'] == code), None)
    v42d = next((r for r in results['v42(ML)'] if r['code'] == code), None)
    if v38d and v42d:
        best = 'v38' if v38d['ret'] >= v42d['ret'] else 'v42'
        print(f'{code:>8} {v38d["trades"]:>4} {v38d["ret"]:>7.2f} {v42d["trades"]:>4} {v42d["ret"]:>7.2f} {best:>6}')
print('Done')
