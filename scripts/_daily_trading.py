# -*- coding: utf-8 -*-
"""实战版每日交易系统 — 信号生成+评分排序+仓位管理"""
import sys, os, json, datetime, pickle
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd, numpy as np

CACHE = Path(r"C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache")
DATA_DIR = Path(__file__).parent / "daily_data"
DATA_DIR.mkdir(exist_ok=True)

# 加载ML模型
_ml_data = pickle.load(open(Path(__file__).parent.parent / "models" / "ml_selector.pkl", "rb"))
_ml_model = _ml_data["model"]
_ml_features = _ml_data["features"]
_ml_threshold = _ml_data.get("threshold", 0.4)

def _load_stock(code):
    """加载单只股票数据"""
    fp = CACHE / f"{code}.parquet"
    if not fp.exists():
        fp2 = CACHE / "cn" / f"{code}.parquet"
        if not fp2.exists(): return None
        fp = fp2
    try:
        df = pd.read_parquet(fp)
        col_map = {"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}
        rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
        df = df.rename(columns=rename)
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date")
        cols = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
        return df[cols].ffill().bfill().dropna().sort_index() if len(cols)==5 else None
    except: return None

def _calc_v42_score(c, o, h, l, v, n, i, code):
    """计算v42 ML增强评分"""
    if i < 20 or i >= n-5: return 0
    limit_up = 0.198 if code.startswith(("300","688")) else 0.098
    streak = 0
    for j in range(max(0,i-10), i):
        if j>0 and c[j]/c[j-1]-1 >= limit_up: streak += 1
        else: streak = 0
    if streak < 2 or not (c[i] < o[i] and c[i]/c[i-1]-1 < limit_up):
        return 0
    vol_ma5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
    vol_r = v[i]/vol_ma5 if vol_ma5>0 else 99
    if i >= 15:
        tr = np.maximum(h[i-14:i]-l[i-14:i],
            np.maximum(abs(h[i-14:i]-c[i-15:i-1]), abs(l[i-14:i]-c[i-15:i-1])))
        atr = np.mean(tr)
    else: atr = 0
    atr_r = atr/c[i] if c[i]>0 and atr>0 else 1
    lc = c[i-streak-1]
    depth = (c[i]-lc)/lc*100
    is_fake = int(c[i] > c[i-1] and c[i] < o[i])
    ma20 = pd.Series(c).rolling(20).mean().values
    ma20_d = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
    ret20 = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0
    s = 0
    if streak == 2: s += 25
    elif streak == 3: s += 22
    elif streak >= 4: s += 12
    if is_fake: s += 25
    else: s += 5
    if atr_r >= 0.08: s += 15
    elif atr_r >= 0.05: s += 10
    if vol_r <= 0.3: s += 15
    elif vol_r <= 0.5: s += 12
    elif vol_r <= 0.7: s += 8
    if depth >= 0: s += 10
    elif depth >= -3: s += 8
    elif depth >= -6: s += 5
    if ma20_d < 15: s += 5
    s = min(100, max(0, s))
    return s if s >= 50 else 0

def _calc_momentum_score(c, v, n, i):
    """动量突破评分"""
    if i < 20: return 0
    high20 = np.max(c[max(0,i-20):i])
    vol_ma20 = np.mean(v[max(0,i-20):i])
    if c[i] >= high20 and v[i] >= vol_ma20 * 1.5:
        ret = (c[i]-c[max(0,i-5)])/c[max(0,i-5)]*100 if i>=5 else 0
        return min(100, max(0, ret*5))
    return 0

def scan_today():
    """全市场扫描，返回今日信号列表（评分降序）"""
    codes = sorted([f.replace(".parquet","") for f in os.listdir(CACHE)
                    if f.endswith(".parquet") and not f.startswith("_")
                    and f[:2] in ("00","30","68")])
    signals = []
    for code in codes:
        df = _load_stock(code)
        if df is None or len(df) < 60: continue
        c = df["Close"].values; o = df["Open"].values
        h = df["High"].values; l = df["Low"].values; v = df["Volume"].values
        n = len(c); i = n - 1
        limit_up = 0.198 if code.startswith(("300","688")) else 0.098
        streak = 0
        for j in range(max(0,n-10), n-1):
            if j>0 and c[j]/c[j-1]-1 >= limit_up: streak += 1
            else: streak = 0
        dragon_score = _calc_v42_score(c, o, h, l, v, n, i, code)
        mom_score = _calc_momentum_score(c, v, n, i)
        total_score = max(dragon_score, mom_score)
        if total_score >= 50:
            signals.append({
                "code": code, "date": str(df.index[-1].date()),
                "price": round(c[-1], 2),
                "dragon_score": dragon_score,
                "momentum_score": mom_score,
                "total_score": total_score,
                "strategy": "龙首阴" if dragon_score > mom_score else "动量突破",
            })
    signals.sort(key=lambda x: -x["total_score"])
    return signals

def allocate(signals, total_cash=100000):
    """仓位分配：只取前N名，按评分比例分配"""
    max_positions = 3
    top = signals[:max_positions]
    if not top: return []
    total_score = sum(s["total_score"] for s in top)
    allocations = []
    for s in top:
        share = s["total_score"] / total_score if total_score > 0 else 1/len(top)
        cash = total_cash * share * 0.95
        shares = int(cash / s["price"] / 100) * 100
        if shares >= 100:
            allocations.append({
                "code": s["code"], "price": s["price"],
                "shares": shares, "amount": round(shares * s["price"], 2),
                "score": s["total_score"], "strategy": s["strategy"],
            })
    return allocations

def run_daily():
    """每日运行入口"""
    print(f"\n{'='*60}")
    print(f"  实战交易系统 -- {datetime.date.today()}")
    print(f"{'='*60}")
    signals = scan_today()
    print(f"全市场扫描: {len(signals)} 个信号")
    if signals:
        print(f"\nTop 10 信号:")
        print(f"  {'代码':>8} {'价格':>8} {'龙首阴':>6} {'动量':>6} {'总分':>6} {'策略':>8}")
        print(f"  {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")
        for s in signals[:10]:
            print(f"  {s['code']:>8} {s['price']:>8.2f} {s['dragon_score']:>6} {s['momentum_score']:>6} {s['total_score']:>6} {s['strategy']:>8}")
        print(f"\n今日买入 (前3名):")
        alloc = allocate(signals)
        for a in alloc:
            print(f"  [BUY] {a['code']} {a['shares']}股 @ {a['price']:.2f} = {a['amount']:.0f}元 ({a['strategy']})")
        out = {"date": str(datetime.date.today()), "signals": signals, "allocations": alloc}
        with open(DATA_DIR / f"daily_{datetime.date.today()}.json", "w") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n已保存: {DATA_DIR / f'daily_{datetime.date.today()}.json'}")
    else:
        print("无信号，空仓等待")
    print("完成")
    return signals

if __name__ == "__main__":
    run_daily()
