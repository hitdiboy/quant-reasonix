# -*- coding: utf-8 -*-
"""全量扫描+ML评分集成+参数网格"""
import sys, os, json, time, pickle
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'

# 1. 全量扫描
print('='*60)
print('  第2轮: 全量扫描')
print('='*60)
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE) if f.endswith('.parquet') and not f.startswith('_') and f[:2] in ('00','30','68')])
t0 = time.time()
candidates = []
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
        if len(df) < 60: continue
    except: continue
    c = df['Close'].values; o = df['Open'].values; v = df['Volume'].values; n = len(c); i = n - 1
    if c[i] > 100: continue
    rng = max(h[i]-l[i], 1)
    cp = (c[i]-l[i])/rng
    v5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
    vr = v[i]/v5 if v5>0 else 1
    ma20 = pd.Series(c).rolling(20).mean().values
    if c[i] > ma20[i] and cp >= 0.6 and vr >= 1.3:
        candidates.append(code)
    if (idx+1) % 500 == 0:
        print(f'  扫描: {idx+1}/{len(files)} 发现={len(candidates)}', flush=True)

print(f'\n全量: {len(files)}只 → 候选: {len(candidates)}只 ({len(candidates)/len(files)*100:.1f}%)')
print(f'耗时: {time.time()-t0:.0f}s')

# 2. ML评分集成
print('\n' + '='*60)
print('  第3轮: ML评分集成')
print('='*60)
_ml_data = pickle.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'ml_selector.pkl'), 'rb'))
_ml_model = _ml_data['model']
_ml_features = _ml_data['features']

# 对候选标的计算ML评分
ml_scores = []
for code in candidates:
    df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
    col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
    rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
    df = df.rename(columns=rename)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.set_index('trade_date')
    df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
    c = df['Close'].values; o = df['Open'].values; v = df['Volume'].values
    h = df['High'].values; l = df['Low'].values; n = len(c); i = n - 1

    limit_up = 0.198 if code[:3] in ('300','688') else 0.098
    streak = 0
    for j in range(max(0,i-10), i):
        if j>0 and c[j]/c[j-1]-1 >= limit_up: streak += 1
        else: streak = 0
    v5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
    vr = v[i]/v5 if v5>0 else 99
    tr = np.maximum(h[i-14:i]-l[i-14:i], np.maximum(abs(h[i-14:i]-c[i-15:i-1]), abs(l[i-14:i]-c[i-15:i-1]))) if i>=15 else 0
    atr_r = np.mean(tr)/c[i] if isinstance(tr, np.ndarray) and c[i]>0 else 1
    lc = c[i-streak-1] if streak>=1 else c[i-1]; depth = (c[i]-lc)/lc*100
    is_fake = int(c[i] > c[i-1] and c[i] < o[i])
    ma20_a = pd.Series(c).rolling(20).mean().values
    ma20_dev = (c[i]-ma20_a[i])/ma20_a[i]*100 if not np.isnan(ma20_a[i]) else 0
    ret20 = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0
    feat = np.array([[streak, vr, depth, atr_r, is_fake, ma20_dev, ret20, c[i]]])
    feat_df = pd.DataFrame(feat, columns=_ml_features).fillna(0)
    ml_p = _ml_model.predict_proba(feat_df)[0,1]
    ml_scores.append({'code':code, 'ml_score':int(ml_p*100), 'price':round(c[i],2)})

ml_scores.sort(key=lambda x: -x['ml_score'])
top5 = ml_scores[:5]
print(f'\nML评分 TOP 5:')
for s in top5:
    print(f'  {s["code"]}: ML={s["ml_score"]}分 价格={s["price"]:.2f}')
print(f'\n候选总数: {len(ml_scores)}')

# 3. 参数网格搜索
print('\n' + '='*60)
print('  第4轮: 参数网格搜索')
print('='*60)

from backtesting import Backtest, Strategy

class EOD(Strategy):
    profit_tgt = 2.5; stop_loss = -2.0; min_vr = 1.3; min_cp = 0.6
    def init(self):
        c=self.data.Close.to_series();h=self.data.High.to_series();l=self.data.Low.to_series();v=self.data.Volume.to_series()
        self.cp=self.I(lambda:((c-l)/(h-l).replace(0,np.nan)).values)
        self.v5=self.I(lambda:v.rolling(5).mean().values);self.m20=self.I(lambda:c.rolling(20).mean().values)
        self._ep=0;self._eb=None
    def next(self):
        if len(self.data)<30:return
        i=len(self.data)-1;ci=float(self.data.Close[-1]);vi=float(self.data.Volume[-1])
        cp=float(self.cp[-1]);v5=float(self.v5[-1]);m20=float(self.m20[-1])
        if not self.position and ci<=100 and ci>m20 and cp>=self.min_cp and vi>=v5*self.min_vr:
            n=int(self.equity*0.2/ci/100)*100
            if n>=100:self.buy(size=n);self._ep=ci;self._eb=i
        if self.position and self._eb is not None and (i-self._eb)>=1:
            pnl=(ci-self._ep)/self._ep*100
            if pnl>=self.profit_tgt or pnl<=self.stop_loss:self.position.close()

codes = ['002432','002164','002211','002178','002400','002456','002229',
         '002529','002855','002553','002418','002667','002951','002181',
         '002725','002943','002316','002512','002272','002348']

params = [
    (2.5, -2.0, 1.3, 0.6),  # 当前
    (2.0, -2.0, 1.5, 0.667), # 收紧
    (3.0, -2.0, 1.3, 0.6),  # 提高止盈
    (2.5, -1.5, 1.3, 0.6),  # 收窄止损
    (2.5, -2.5, 1.3, 0.6),  # 放宽止损
]

print(f'{"TP":>5} {"SL":>5} {"VR":>5} {"CP":>5} {"交易数":>6} {"均收益":>8} {"正比":>6}')
print('-' * 45)
for tp, sl, vr, cp in params:
    rets = []
    for code in codes:
        df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
        col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
        rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
        df = df.rename(columns=rename)
        if 'trade_date' in df.columns: df['trade_date'] = pd.to_datetime(df['trade_date']); df = df.set_index('trade_date')
        df = df[['Open','High','Low','Close','Volume']].dropna().sort_index(); df.index.name = 'Date'
        if len(df) < 60: continue
        Strat = type('T', (EOD,), {'stock_code': code, 'profit_tgt': tp, 'stop_loss': sl, 'min_vr': vr, 'min_cp': cp})
        r = Backtest(df, Strat, cash=100000, commission=0.0003).run()
        if r['# Trades'] > 0: rets.append(r['Return [%]'])
    avg = np.mean(rets) if rets else 0
    pos = sum(1 for r in rets if r>0)/len(rets)*100 if rets else 0
    print(f'{tp:>5.1f} {sl:>5.1f} {vr:>5.1f} {cp:>5.2f} {len(rets):>6} {avg:>+8.2f}% {pos:>5.0f}%')

print('\n全部完成')