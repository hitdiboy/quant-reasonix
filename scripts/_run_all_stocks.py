# -*- coding: utf-8 -*-
"""全量回测：遍历所有中小板+科创板"""
import sys, os, time, pandas as pd, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from backtesting import Backtest
from strategies.custom.strategy_001_dragon_first_yin import DragonFirstYin

CACHE_BASE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'

files = sorted([f.replace(".parquet","") for f in os.listdir(CACHE_BASE)
         if f.endswith(".parquet") and not f.startswith("_")
         and f[:3] in ("688","002")])

board_data = {"科创板":[],"中小板":[]}
total_signal = 0
start_ts = time.time()
total = len(files)

print(f"全量回测开始：{total}只股票（中小板+科创板）")
print("=" * 90)

for idx, code in enumerate(files):
    path = os.path.join(CACHE_BASE, f"{code}.parquet")
    try:
        df = pd.read_parquet(path)
        rename = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl in ("open","open_p"): rename[c]="Open"
            elif cl in ("high","high_p"): rename[c]="High"
            elif cl in ("low","low_p"): rename[c]="Low"
            elif cl in ("close","close_p"): rename[c]="Close"
            elif cl in ("volume","vol"): rename[c]="Volume"
        df = df.rename(columns=rename)
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date")
        cols = [c for c in ("Open","High","Low","Close","Volume") if c in df.columns]
        if len(cols) < 5: continue
        df = df[cols].dropna().sort_index()
        df.index.name = "Date"
        if len(df) < 200: continue

        board = DragonFirstYin.classify_board(code)
        Strat = type("Temp", (DragonFirstYin,), {"stock_code": code})
        bt = Backtest(df, Strat, cash=100000, commission=0.0003)
        res = bt.run()

        if res["# Trades"] > 0:
            total_signal += 1
            board_data[board].append({
                "code": code,
                "trades": res["# Trades"],
                "ret": res["Return [%]"],
                "sharpe": res.get("Sharpe Ratio", 0),
                "wr": res.get("Win Rate [%]", 0),
            })
    except:
        pass

    if (idx + 1) % 100 == 0 or idx == total - 1:
        pct = (idx+1)/total*100
        elapsed = time.time() - start_ts
        print(f"  {idx+1}/{total} ({pct:.0f}%) signal={total_signal} {elapsed:.0f}s")

elapsed = round(time.time() - start_ts, 1)
print()
print("=" * 90)
print("全量回测结果")
print("=" * 90)
print(f"总样本 {total}只  有信号 {total_signal}只")
print()

for board in ["科创板","中小板"]:
    prefix = "688" if board == "科创板" else "002"
    records = board_data[board]
    n = sum(1 for c in files if c[:3] == prefix)
    if not records:
        print(f"{board}: {n}只  信号=0")
        continue
    rets = [r["ret"] for r in records]
    positive = sum(1 for r in rets if r > 0)
    avg_ret = np.mean(rets)
    med_ret = np.median(rets)
    shp = [r["sharpe"] for r in records if not np.isnan(r["sharpe"])]
    avg_shp = np.mean(shp) if shp else 0
    wr_vals = [r["wr"] for r in records if not np.isnan(r["wr"])]
    avg_wr = np.mean(wr_vals) if wr_vals else 0
    neg = sum(1 for r in rets if r < 0)
    zero = sum(1 for r in rets if r == 0)
    print(f"{board}: {n}只  信号={len(records)}, 正{positive}, 负{neg}, 平{zero}")
    print(f"      正占比{positive/len(records)*100:.1f}%, 胜率={avg_wr:.1f}%, 平均收益={avg_ret:.2f}%, 中位收益={med_ret:.2f}%, 夏普={avg_shp:.3f}")
    top5 = sorted(records, key=lambda r: r["ret"], reverse=True)[:5]
    codes = ", ".join(f'{r["code"]}(+{r["ret"]:.1f}%)' for r in top5)
    print(f"      前5: {codes}")

print()
print(f"耗时: {elapsed}s")
print("完成")