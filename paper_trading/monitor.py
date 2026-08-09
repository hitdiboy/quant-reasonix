import sys, os, duckdb, pandas as pd
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.fetch.unified import fetch
from backtesting import Backtest
from strategies.factory import StrategyFactory
from strategies.momentum import Momentum
from strategies.triple_ma import TripleMA
from strategies.dual_momentum import DualMomentum
from strategies.grid_trading import GridTrading
from strategies.ma_cross import MaCross
from strategies.turtle_trading import TurtleTrading

def parse_params(vname, sclass):
    keys = sorted(sclass.params.keys())
    cn = sclass.name or sclass.__name__
    rest = vname[len(cn)+1:]
    out = {}
    for k in keys:
        if not rest.startswith(k): break
        vs = rest[len(k):]
        i = vs.find("_")
        if i >= 0:
            vp, rest = vs[:i], vs[i+1:]
        else:
            vp, rest = vs, ""
        try: out[k] = int(vp) if "." not in vp else float(vp)
        except: out[k] = vp
    return out

factory = StrategyFactory()
for sc in [Momentum, TripleMA, DualMomentum, GridTrading, MaCross, TurtleTrading]:
    factory.register(sc)
reg = factory._registry

db = duckdb.connect('C:/Users/Administrator/Codex-Workspace/quant-codex/results/vault.db')
sql = '''SELECT strategy_name,symbol,sharpe_ratio,return_pct,max_drawdown_pct,num_trades
FROM (
  SELECT strategy_name,symbol,sharpe_ratio,return_pct,max_drawdown_pct,num_trades,
         ROW_NUMBER() OVER (PARTITION BY strategy_name,symbol ORDER BY sharpe_ratio DESC) AS rn
  FROM backtest_runs
  WHERE sharpe_ratio>0.5 AND max_drawdown_pct>-60 AND num_trades>5
) s WHERE rn=1
ORDER BY sharpe_ratio DESC LIMIT 10'''
strategies = db.execute(sql).fetchdf()
db.close()

now = datetime.now().strftime('%Y-%m-%d')
print(f'==== Monitor {now} ====')
print()

for _, r in strategies.iterrows():
    sym, sname = r.symbol, r.strategy_name
    cls_name = sname.split("_")[0]
    data = fetch(sym)
    if data is None or len(data) < 50:
        print(f'  {sname[:30]:>30s} {sym:>6s}  SKIP - no data')
        continue
    target = None
    for n, c in reg.items():
        if cls_name.lower() in n.lower():
            target = c
            break
    if target is None:
        print(f'  {sname[:30]:>30s} {sym:>6s}  SKIP - no class')
        continue
    params = parse_params(sname, target)
    bt = Backtest(data, target, cash=100000, commission=0.0003, finalize_trades=True)
    r_new = bt.run(**params)
    so = round(r.sharpe_ratio, 3)
    sn = round(r_new['Sharpe Ratio'], 3)
    ro = round(r.return_pct, 1)
    rn = round(r_new['Return [%]'], 1)
    ddo = round(r.max_drawdown_pct, 1)
    ddn = round(r_new['Max. Drawdown [%]'], 1)
    to = r.num_trades
    tn = r_new['# Trades']
    arrow = '+' if sn >= so else '-'
    print(f'  {sname[:30]:>30s} {sym:>6s}  Sharpe: {so}->{sn}({arrow}{round(abs(sn-so),3)})  Ret: {ro}->{rn}  DD: {ddo}->{ddn}  Trades: {to}->{tn}')

print()
print('Done')