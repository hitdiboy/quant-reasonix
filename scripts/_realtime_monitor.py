# -*- coding: utf-8 -*-
"""盘中实时监控系统"""

import sys, os, json, time, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd, numpy as np
from data.fetch.tencent_realtime import get_realtime_quotes

BASE = Path(__file__).parent.parent
CACHE = Path(r"C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache")
CONFIG = json.load(open(BASE / "config" / "eod_strategy.json"))
DATA_DIR = Path(__file__).parent / "daily_data"
DATA_DIR.mkdir(exist_ok=True)

MIN_CP = CONFIG.get("min_close_pos", 0.6)
MIN_VR = CONFIG.get("min_vol_ratio", 1.3)
MAX_PX = CONFIG.get("max_price", 100)
MIN_SCORE = CONFIG.get("min_score", 60)


def is_market_hours():
    t = datetime.datetime.now()
    if t.weekday() >= 5:
        return False
    m = t.hour * 100 + t.minute
    return (925 <= m <= 1130) or (1300 <= m <= 1500)


def is_final_phase():
    t = datetime.datetime.now()
    m = t.hour * 100 + t.minute
    return 1430 <= m <= 1500


def prescan():
    """开盘前：用缓存数据预筛候选池"""
    codes = sorted([f.replace(".parquet", "") for f in os.listdir(CACHE)
                    if f.endswith(".parquet") and not f.startswith("_")
                    and f[:2] in ("00", "30", "68")])
    candidates = []
    for idx, code in enumerate(codes):
        try:
            df = pd.read_parquet(CACHE / f"{code}.parquet")
            col_map = {"open": "Open", "high": "High", "low": "Low",
                       "close": "Close", "volume": "Volume"}
            rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns
                      if c.lower().strip() in col_map}
            df = df.rename(columns=rename)
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.set_index("trade_date")
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df = df.dropna().sort_index()
            if len(df) < 60:
                continue
        except:
            continue

        c = df["Close"].values
        h = df["High"].values
        l = df["Low"].values
        o = df["Open"].values
        v = df["Volume"].values
        n = len(c)
        i = n - 1

        if c[i] > MAX_PX:
            continue
        rng = h[i] - l[i] if h[i] > l[i] else 1
        cp = (c[i] - l[i]) / rng
        v5 = np.mean(v[max(0, i-5):i]) if i >= 5 else np.mean(v[:i])
        vr = v[i] / v5 if v5 > 0 else 1
        ma20 = pd.Series(c).rolling(20).mean().values
        if not np.isnan(ma20[i]) and c[i] > ma20[i] and cp >= MIN_CP and vr >= MIN_VR:
            candidates.append(code)

        if (idx + 1) % 500 == 0:
            print(f"  预筛: {idx+1}/{len(codes)} 候选={len(candidates)}", flush=True)

    return candidates


def check_candidates(codes):
    """盘中实时检查候选列表"""
    signals = []
    batch_size = 50
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        quotes = get_realtime_quotes(batch)
        for code in batch:
            q = quotes.get(code)
            if not q:
                continue
            px = q.get("price", 0)
            if px <= 0 or px > MAX_PX:
                continue
            chg = q.get("change_pct", 0)
            op = q.get("open", px)
            hi = q.get("high", px)
            lo = q.get("low", px)
            rng = hi - lo if hi > lo else 1
            cp = (px - lo) / rng
            vol = q.get("volume", 0)
            name = q.get("name", code)
            if cp >= MIN_CP and chg >= 0:
                signals.append({
                    "code": code, "name": name, "price": px,
                    "change_pct": round(chg, 2), "close_pos": round(cp, 2),
                    "volume": vol
                })
        time.sleep(0.3)
    signals.sort(key=lambda x: -x["close_pos"])
    return signals


def run():
    if not is_market_hours():
        print("非交易时段，程序退出")
        return

    print("=" * 60)
    print("  尾盘战法 -- 盘中实时监控")
    print("=" * 60)

    # 预筛候选
    t0 = time.time()
    candidates = prescan()
    print(f"\n预筛完成: {len(candidates)}只候选 ({time.time()-t0:.0f}s)")

    if len(candidates) == 0:
        print("今日无候选，空仓等待")
        return

    # 保存预筛名单
    with open(DATA_DIR / f"prescan_{datetime.date.today()}.json", "w") as f:
        json.dump({"date": str(datetime.date.today()),
                   "candidates": candidates}, f, ensure_ascii=False, indent=2)

    # 盘中循环
    last_minute = ""
    final_signals = []
    rounds = 0

    while is_market_hours():
        now = datetime.datetime.now()
        hm = f"{now.hour:02d}:{now.minute:02d}"

        interval = 1 if is_final_phase() else 5
        if hm == last_minute:
            time.sleep(1)
            continue

        current_min = now.minute
        if current_min % interval != 0 and not is_final_phase():
            time.sleep(1)
            continue

        last_minute = hm
        rounds += 1

        signals = check_candidates(candidates)
        print(f"\n[{hm}] 第{rounds}轮 | {len(signals)}只信号")

        if signals:
            for s in signals[:5]:
                print(f"  {s['code']} {s['name'][:8]:>8s} "
                      f"{s['price']:>7.2f} 涨{s['change_pct']:>+6.2f}% "
                      f"尾盘{s['close_pos']:.2f}")
            if len(signals) > 5:
                print(f"  ...还有{len(signals)-5}只")

        if is_final_phase():
            final_signals = signals
            print(f"\n{'='*60}")
            print(f"  尾盘决战 ({hm}) -- {len(final_signals)}只最终信号")
            print(f"{'='*60}")
            if final_signals:
                top = final_signals[:3]
                for s in top:
                    print(f"  >>> BUY {s['code']} {s['name'][:8]:>8s} "
                          f"@{s['price']:.2f} 尾盘{s['close_pos']:.2f}")
                out = {"date": str(datetime.date.today()), "time": hm,
                       "signals": top}
                with open(DATA_DIR / f"final_{datetime.date.today()}.json", "w") as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
                print(f"\n  已保存: {DATA_DIR / f'final_{datetime.date.today()}.json'}")
            else:
                print("  今日无信号，空仓")
            break

        time.sleep(2)

    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 收盘")


if __name__ == "__main__":
    run()
