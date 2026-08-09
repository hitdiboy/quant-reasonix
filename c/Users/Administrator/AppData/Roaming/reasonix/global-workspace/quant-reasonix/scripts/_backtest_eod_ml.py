# -*- coding: utf-8 -*-
"""尾盘战法 ML增强版 — 完整回测"""
import sys, os, pickle, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np
from backtesting import Backtest
from strategies._base import BaseStrategy

# Load ML model
_ml_data = pickle.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'ml_selector.pkl'), 'rb'))
_ml_model = _ml_data['model']
_ml_features = _ml_data['features']

class EODML(BaseStrategy):
    name = "尾盘战法ML"
    stock_code = ""
    min_vr = 1.3; min_cp = 0.6; min_body = 0.2
    profit_tgt = 2.5; stop_loss = -2.0; max_hold = 1
    max_price = 100; ml_weight = 0.7; min_total = 70
    
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
        self._s_close = c.values; self._s_high = h.values
        self._s_low = l.values; self._s_open = o.values; self._s_vol = v.values
        self._ep = 0; self._eb = None
        
    def _ml_score(self, i):
        if i < 20: return 50
        c = self._s_close; h = self._s_high; l = self._s_low
        o = self._s_open; v = self._s_vol
        limit_up = 0.198 if self.stock_code[:3] in ('300','688') else 0.098
        streak = 0
        for j in range(max(0,i-10), i):
            if j>0 and c[j]/c[j-1]-1 >= limit_up: streak += 1
            else: streak = 0
        v5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
        vr = v[i]/v5 if v5>0 else 99
        if i >= 15:
            tr = np.maximum(h[i-14:i]-l[i-14:i],
                np.maximum(abs(h[i-14:i]-c[i-15:i-1]), abs(l[i-14:i]-c[i-15:i-1])))
            atr = np.mean(tr)
        else: atr = 0
        atr_r = atr/c[i] if c[i]>0 and atr>0 else 1
        lc = c[i-streak-1] if streak>=1 else c[i-1]
        depth = (c[i]-lc)/lc*100
        is_fake = int(c[i] > c[i-1] and c[i] < o[i])
        ma20 = pd.Series(c).rolling(20).mean().values
        ma20_dev = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
        ret20 = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0
        feat = np.array([[streak, vr, depth, atr_r, is_fake, ma20_dev, ret20, c[i]]])
        feat_df = pd.DataFrame(feat, columns=_ml_features).fillna(0)
        return int(_ml_model.predict_proba(feat_df)[0, 1] * 100)
    
    def next(self):
        if len(self.data) < 30: return
        i = len(self.data)-1
        c = self._s_close; h = self._s_high; l = self._s_low
        o = self._s_open; v = self._s_vol
        ci = float(self.data.Close[-1]); vi = float(self.data.Volume[-1])
        rng = h[i]-l[i] if h[i]>l[i] else 1
        cp = (c[i]-l[i])/rng; body = abs(c[i]-o[i])/rng; up = c[i] > o[i]
        v5 = float(self.v5[-1]); m20 = float(self.m20[-1])
        m60 = float(self.m60[-1]) if not np.isnan(float(self.m60[-1])) else 0
        
        if not self.position:
            if ci > self.max_price: return
            s1 = (10 if up else 0) + (10 if cp>=0.6 else 5 if cp>=0.5 else 0) + (10 if body>=0.2 else 5 if body>=0.15 else 0)
            vr = vi/v5 if v5>0 else 1
            s2 = (15 if vr>=2.0 else 10 if vr>=1.5 else 5 if vr>=1.3 else 0) + (10 if vr>=1.5 else 5 if vr>=1.2 else 0)
            s3 = (10 if not np.isnan(m20) and ci>m20 else 0)+(5 if not np.isnan(m60) and ci>m60 else 0)+(5 if c[i]>c[max(0,i-5)] else 0)
            s4 = 15+(5 if vr<=3.0 else 0)+(5 if (c[i]-c[max(0,i-5)])/c[max(0,i-5)]*100>-5 else 0)+(5 if ci<50 else 3 if ci<80 else 0)
            s4 = min(s4, 25)
            rule = min(s1+s2+s3+s4, 100)
            ml = self._ml_score(i)
            total = int(ml*self.ml_weight + rule*(1-self.ml_weight))
            if total >= self.min_total:
                n = int(self.equity*0.2/ci/100)*100
                if n >= 100: self.buy(size=n); self._ep = ci; self._eb = i
        
        if self.position and self._eb is not None and (i-self._eb) >= 1:
            pnl = (ci-self._ep)/self._ep*100
            if pnl >= self.profit_tgt or pnl <= self.stop_loss or (i-self._eb) >= self.max_hold:
                self.position.close()

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
codes = ['002432','002164','002211','002178','002400','002456','002229',
         '002529','002855','002553','002418','002667','002951','002181',
         '002725','002943','002316','002512','002272','002348']

print("="*60)
print("  尾盘战法 ML增强版 — 参数优化回测")
print("="*60)

params = [
    (0.7, 70, 100), (0.7, 75, 80), (0.6, 65, 100),
    (0.8, 75, 100), (0.7, 70, 50),
]

for mw, mt, mp in params:
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
        if len(df) < 60: continue
        Strat = type('T', (EODML,), {'stock_code': code, 'ml_weight': mw, 'min_total': mt, 'max_price': mp})
        bt = Backtest(df, Strat, cash=100000, commission=0.0003)
        r = bt.run()
        if r['# Trades'] > 0:
            rets.append(r['Return [%]'])
    avg = np.mean(rets) if rets else 0
    pos = sum(1 for r in rets if r>0)/len(rets)*100 if rets else 0
    print(f"ML={mw} Thr={mt} Pmax={mp}: traded={len(rets)} avg={avg:+.2f}% pos={pos:.0f}%")

print("\nDone")