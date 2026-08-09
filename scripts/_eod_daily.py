# -*- coding: utf-8 -*-
"""尾盘隔夜战法 -- 实战版每日选股系统 v1.0"""
import sys, os, json, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd, numpy as np

CACHE = Path(r"C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache")
DATA_DIR = Path(__file__).parent / "daily_data"
DATA_DIR.mkdir(exist_ok=True)

def calc_tail_score(code):
    """五维评分 (0-100): 尾盘形态30 + 量能确认25 + 均线位置20 + 风险控制25"""
    fp = CACHE / f"{code}.parquet"
    if not fp.exists():
        fp2 = CACHE / "cn" / f"{code}.parquet"
        if not fp2.exists(): return None
        fp = fp2
    try:
        df = pd.read_parquet(fp)
        col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
        rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
        df = df.rename(columns=rename)
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.set_index('trade_date')
        df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
        if len(df) < 30: return None
    except: return None

    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    o = df['Open'].values; v = df['Volume'].values; n = len(c); i = n - 1
    rng = h[i] - l[i] if h[i] > l[i] else 1

    # D1: 尾盘形态 (30分)
    close_pos = (c[i] - l[i]) / rng
    body = abs(c[i] - o[i]) / rng
    is_up = c[i] > o[i]
    s1 = 0
    if is_up: s1 += 10
    if close_pos >= 0.667: s1 += 10
    elif close_pos >= 0.5: s1 += 5
    if body >= 0.5: s1 += 10
    elif body >= 0.3: s1 += 5
    s1 = min(s1, 30)

    # D2: 量能确认 (25分)
    v5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
    v20 = np.mean(v[max(0,i-20):i]) if i>=20 else np.mean(v[:i])
    vr = v[i]/v5 if v5>0 else 1
    vr20 = v[i]/v20 if v20>0 else 1
    s2 = 0
    if vr >= 2.0: s2 += 15
    elif vr >= 1.5: s2 += 10
    elif vr >= 1.3: s2 += 5
    if vr20 >= 1.5: s2 += 10
    elif vr20 >= 1.2: s2 += 5
    s2 = min(s2, 25)

    # D3: 均线位置 (20分)
    ma5 = pd.Series(c).rolling(5).mean().values
    ma20 = pd.Series(c).rolling(20).mean().values
    ma60 = pd.Series(c).rolling(60).mean().values
    s3 = 0
    if c[i] > ma20[i] and not np.isnan(ma20[i]): s3 += 10
    if not np.isnan(ma60[i]) and c[i] > ma60[i]: s3 += 5
    if not np.isnan(ma5[i]) and not np.isnan(ma20[i]) and ma5[i] > ma20[i]: s3 += 5
    s3 = min(s3, 20)

    # D4: 风险控制 (25分)
    s4 = 15
    if vr <= 3.0: s4 += 5
    ret5 = (c[i]-c[max(0,i-5)])/c[max(0,i-5)]*100 if i>=5 else 0
    if ret5 > -5: s4 += 5
    if c[i] < 100: s4 += 5
    s4 = min(s4, 25)

    total = s1 + s2 + s3 + s4
    return {'code':code, 'price':round(c[i],2), 'date':str(df.index[-1].date()),
            's1(tail)':s1, 's2(vol)':s2, 's3(MA)':s3, 's4(risk)':s4,
            'total':total,
            'detail':{'cp':round(close_pos,2),'body':round(body,2),'is_up':is_up,
                      'vr':round(vr,2),'vr20':round(vr20,2),'ret5':round(ret5,2)}}

def scan_and_select(top_n=3, min_score=60):
    """全市场扫描 + 选股排名"""
    codes = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
                    if f.endswith('.parquet') and not f.startswith('_')
                    and f[:2] in ('00','30','68')])
    candidates = []
    for code in codes:
        result = calc_tail_score(code)
        if result and result['total'] >= min_score:
            candidates.append(result)
    candidates.sort(key=lambda x: -x['total'])

    print(f"\n{'='*60}")
    print(f"  尾盘隔夜战法 -- {datetime.date.today()}")
    print(f"{'='*60}")
    print(f"扫描: {len(codes)}只 | 候选: {len(candidates)}只\n")
    if candidates:
        print(f"  {'代码':>8} {'价格':>8} {'总分':>6} {'尾盘':>6} {'量能':>6} {'均线':>6} {'风控':>6}")
        print(f"  {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
        for s in candidates[:10]:
            print(f"  {s['code']:>8} {s['price']:>8.2f} {s['total']:>6} {s['s1(tail)']:>6} {s['s2(vol)']:>6} {s['s3(MA)']:>6} {s['s4(risk)']:>6}")
        print(f"\n今日买入 (Top {top_n}):")
        for s in candidates[:top_n]:
            n_shares = int(100000/top_n/s['price']/100)*100
            if n_shares >= 100:
                print(f"  [BUY] {s['code']} {n_shares}股 @ {s['price']:.2f} = {n_shares*s['price']:.0f}元")
    else:
        print("无达标信号，空仓等待")

    out = {'date':str(datetime.date.today()), 'top':candidates[:top_n], 'all':candidates[:20]}
    with open(DATA_DIR / f"eod_{datetime.date.today()}.json", 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return candidates

if __name__ == '__main__':
    scan_and_select()