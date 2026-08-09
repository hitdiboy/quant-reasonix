# -*- coding: utf-8 -*-
"""尾盘隔夜战法 v1.2 — ML增强版"""
import sys, os, json, datetime, pickle
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd, numpy as np

CACHE = Path(r"C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache")
CONFIG = json.load(open(Path(__file__).parent.parent / "config" / "eod_strategy.json"))
DATA_DIR = Path(__file__).parent / "daily_data"
DATA_DIR.mkdir(exist_ok=True)

MIN_SCORE = CONFIG.get("min_score", 85)
MAX_POS = CONFIG.get("max_positions", 3)

# Load ML model
_ml_data = pickle.load(open(Path(__file__).parent.parent / "models" / "ml_selector.pkl", "rb"))
_ml_model = _ml_data["model"]
_ml_features = _ml_data["features"]

def calc_tail_score(code):
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

    # --- Rule-based score (五维评分) ---
    close_pos = (c[i] - l[i]) / rng
    body = abs(c[i] - o[i]) / rng
    is_up = c[i] > o[i]
    s1 = 0
    if is_up: s1 += 10
    if close_pos >= 0.75: s1 += 10
    elif close_pos >= 0.5: s1 += 5
    if body >= 0.35: s1 += 10
    elif body >= 0.25: s1 += 5
    s1 = min(s1, 30)

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

    ma20 = pd.Series(c).rolling(20).mean().values
    ma60 = pd.Series(c).rolling(60).mean().values
    ma5 = pd.Series(c).rolling(5).mean().values
    s3 = 0
    if not np.isnan(ma20[i]) and c[i] > ma20[i]: s3 += 10
    if not np.isnan(ma60[i]) and c[i] > ma60[i]: s3 += 5
    if not np.isnan(ma5[i]) and not np.isnan(ma20[i]) and ma5[i] > ma20[i]: s3 += 5
    s3 = min(s3, 20)

    s4 = 15
    if vr <= 3.0: s4 += 5
    ret5 = (c[i]-c[max(0,i-5)])/c[max(0,i-5)]*100 if i>=5 else 0
    if ret5 > -5: s4 += 5
    if c[i] < 30: s4 += 5
    elif c[i] < 60: s4 += 3
    s4 = min(s4, 25)
    rule_score = s1 + s2 + s3 + s4

    if c[i] > 100: return None
    # --- ML score ---
    if i >= 20:
        limit_up = 0.198 if code.startswith(("300","688")) else 0.098
        streak = 0
        for j in range(max(0,i-10), i):
            if j>0 and c[j]/c[j-1]-1 >= limit_up: streak += 1
            else: streak = 0
        if i >= 15:
            tr = np.maximum(h[i-14:i]-l[i-14:i],
                np.maximum(abs(h[i-14:i]-c[i-15:i-1]), abs(l[i-14:i]-c[i-15:i-1])))
            atr = np.mean(tr)
        else: atr = 0
        atr_r = atr/c[i] if c[i]>0 and atr>0 else 1
        lc2 = c[i-streak-1] if streak>=1 else c[i-1]
        depth = (c[i]-lc2)/lc2*100
        is_fake = int(c[i] > c[i-1] and c[i] < o[i])
        ma20_dev = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
        ret20 = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0
        feat = np.array([[streak, vr, depth, atr_r, is_fake, ma20_dev, ret20, c[i]]])
        feat_df = pd.DataFrame(feat, columns=_ml_features).fillna(0)
        ml_score = int(_ml_model.predict_proba(feat_df)[0, 1] * 100)
    else:
        ml_score = rule_score

    # 综合评分 = ML评分(70%) + 规则评分(30%)
    total = int(ml_score * 0.7 + rule_score * 0.3)
    if total < MIN_SCORE: return None

    return {
        'code': code, 'price': round(c[i], 2), 'date': str(df.index[-1].date()),
        'total': total, 'ml_score': ml_score, 'rule_score': rule_score,
        's1_tail': s1, 's2_vol': s2, 's3_ma': s3, 's4_risk': s4,
        'detail': {'cp': round(close_pos, 2), 'body': round(body, 2),
                   'is_up': bool(is_up), 'vr': round(vr, 2), 'ret5': round(ret5, 2)}
    }

def scan_and_select():
    codes = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
                    if f.endswith('.parquet') and not f.startswith('_')
                    and f[:2] in ('00','30','68')])
    candidates = []
    for code in codes:
        r = calc_tail_score(code)
        if r: candidates.append(r)
    candidates.sort(key=lambda x: -x['total'])

    print(f"\n{'='*60}")
    print(f"  尾盘隔夜战法 v1.2(ML增强) -- {datetime.date.today()}")
    print(f"{'='*60}")
    print(f"扫描: {len(codes)}只 | 候选: {len(candidates)}只 (阈值≥{MIN_SCORE})")
    if candidates:
        print(f"\nTop 10:")
        print(f"  {'代码':>8} {'价格':>8} {'总分':>6} {'ML':>6} {'规则':>6} {'尾盘':>6} {'量能':>6} {'均线':>6}")
        print(f"  {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
        for s in candidates[:10]:
            print(f"  {s['code']:>8} {s['price']:>8.2f} {s['total']:>6} {s['ml_score']:>6} {s['rule_score']:>6} {s['s1_tail']:>6} {s['s2_vol']:>6} {s['s3_ma']:>6}")
        print(f"\n今日买入 (Top {MAX_POS}):")
        for s in candidates[:MAX_POS]:
            n_shares = int(100000/MAX_POS/s['price']/100)*100
            if n_shares >= 100:
                print(f"  [BUY] {s['code']} {n_shares}股 @ {s['price']:.2f} = {n_shares*s['price']:.0f}元")
        out = {'date': str(datetime.date.today()), 'top': candidates[:MAX_POS], 'all': candidates[:20]}
        fp_out = DATA_DIR / f"eod_{datetime.date.today()}.json"
        with open(fp_out, 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n已保存: {fp_out}")
    else:
        print("无达标信号，空仓等待")
    return candidates

if __name__ == '__main__':
    scan_and_select()