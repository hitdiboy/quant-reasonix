# -*- coding: utf-8 -*-
"""尾盘战法参数优化回测"""
import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtesting import Backtest
from strategies._base import BaseStrategy

class EODV02(BaseStrategy):
    name = "尾盘战法v02"
    stock_code = ""
    min_vol_r = 1.5
    min_cp = 0.667
    min_body = 0.2
    req_ma60 = False
    tp = 2.0
    sl = -2.0
    def init(self):
        c = self.data.Close.to_series(); h = self.data.High.to_series()
        l = self.data.Low.to_series(); o = self.data.Open.to_series()
        v = self.data.Volume.to_series()
        self.cp = self.I(lambda: ((c-l)/(h-l).replace(0,np.nan)).values)
        self.br = self.I(lambda: (abs(c-o)/(h-l).replace(0,np.nan)).values)
        self.up = self.I(lambda: (c>o).values.astype(float))
        self.v5 = self.I(lambda: v.rolling(5).mean().values)
        self.m20 = self.I(lambda: c.rolling(20).mean().values)
        self.m60 = self.I(lambda: c.rolling(60).mean().values)
        self._ep = 0; self._eb = None
    def next(self):
        if len(self.data) < 30: return
        i = len(self.data)-1
        c = float(self.data.Close[-1]); v = float(self.data.Volume[-1])
        cp = float(self.cp[-1]); up = bool(self.up[-1])
        v5 = float(self.v5[-1]); m20 = float(self.m20[-1])
        m60 = float(self.m60[-1]) if not np.isnan(float(self.m60[-1])) else 0
        if not self.position:
            ok = (v >= v5*self.min_vol_r if v5>0 else False) and cp >= self.min_cp
            ok = ok and up and c > m20
            if self.req_ma60 and m60 > 0: ok = ok and c > m60
            if ok:
                n = int(self.equity*0.2/c/100)*100
                if n >= 100: self.buy(size=n); self._ep = c; self._eb = i
        if self.position and self._eb is not None and (i-self._eb) >= 1:
            pnl = (c-self._ep)/self._ep*100
            if pnl >= self.tp or pnl <= self.sl or (i-self._eb) >= 1:
                self.position.close()

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
codes = ['002432','002164','002211','002178','002400','002456','002229',
         '002529','002855','002553','002418','002667','002951','002181',
         '002725','002943','002316','002512','002272','002348']

params = [
    {'min_vol_r':1.5,'min_cp':0.667,'tp':2.0,'sl':-2.0,'req_ma60':False},
    {'min_vol_r':2.0,'min_cp':0.7,'tp':2.5,'sl':-2.5,'req_ma60':False},
    {'min_vol_r':1.5,'min_cp':0.667,'tp':3.0,'sl':-2.0,'req_ma60':True},
    {'min_vol_r':1.3,'min_cp':0.6,'tp':2.0,'sl':-1.5,'req_ma60':False},
]

best = None
for p in params:
    rets = []
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
        Strat = type('T', (EODV02,), {'stock_code': code, **p})
        try:
            r = Backtest(df, Strat, cash=100000, commission=0.0003).run()
            if r['# Trades'] > 0: rets.append(r['Return [%]'])
        except: pass
    avg = np.mean(rets) if rets else 0
    pos = sum(1 for r in rets if r>0)/len(rets)*100 if rets else 0
    desc = f"VR={p['min_vol_r']} CP={p['min_cp']} TP={p['tp']} SL={p['sl']} MA60={p['req_ma60']}"
    print(f"{desc}: trades={len(rets)} avg={avg:+.2f}% pos={pos:.0f}%")
    if best is None or avg > best[0]: best = (avg, desc, p)

print(f"\nBest: {best[1]} -> avg={best[0]:+.2f}%")
