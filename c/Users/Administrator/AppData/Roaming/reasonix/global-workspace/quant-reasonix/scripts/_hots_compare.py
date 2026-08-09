# -*- coding: utf-8 -*-
"""热点板块 vs 传统标的尾盘战法对比"""
import sys, os, json, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtesting import Backtest, Strategy

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'

hot_codes = {
    "创新药/CXO": ["603259","002821","300759","300347"],
    "PCB/半导体": ["002463","002916","002436"],
    "AI/CPO/光模块": ["300308","300502","300394"],
    "半导体/芯片": ["002371","603986"],
    "商业航天": ["600118","600879"],
    "机器人": ["688017","603728"],
}
standard = ["002432","002164","002211","002178","002400","002456",
            "002855","002553","002725","002943"]

class EOD(Strategy):
    def init(self):
        c=self.data.Close.to_series();h=self.data.High.to_series()
        l=self.data.Low.to_series();v=self.data.Volume.to_series()
        self.cp=self.I(lambda:((c-l)/(h-l).replace(0,np.nan)).values)
        self.v5=self.I(lambda:v.rolling(5).mean().values)
        self.m20=self.I(lambda:c.rolling(20).mean().values)
        self._ep=0;self._eb=None
    def next(self):
        if len(self.data)<30:return
        i=len(self.data)-1;ci=float(self.data.Close[-1]);vi=float(self.data.Volume[-1])
        cp=float(self.cp[-1]);v5=float(self.v5[-1]);m20=float(self.m20[-1])
        if not self.position and ci<=100 and ci>m20 and cp>=0.6 and vi>=v5*1.3:
            n=int(self.equity*0.2/ci/100)*100
            if n>=100:self.buy(size=n);self._ep=ci;self._eb=i
        if self.position and self._eb is not None and (i-self._eb)>=1:
            pnl=(ci-self._ep)/self._ep*100
            if pnl>=2.5 or pnl<=-2.0:self.position.close()

def test_codes(label, codes):
    results = []
    for code in codes:
        try:
            df = pd.read_parquet(f"{CACHE}/{code}.parquet")
            col_map = {"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}
            rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
            df = df.rename(columns=rename)
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.set_index("trade_date")
            df = df[["Open","High","Low","Close","Volume"]].dropna().sort_index()
            df.index.name = "Date"
            if len(df) < 60: continue
        except: continue
        Strat = type("T", (EOD,), {"stock_code": code})
        r = Backtest(df, Strat, cash=100000, commission=0.0003).run()
        if r["# Trades"] > 0:
            results.append({"code":code, "trades":int(r["# Trades"]),
                            "ret":round(r["Return [%]"],2),
                            "sharpe":r.get("Sharpe Ratio",0),
                            "wr":r.get("Win Rate [%]",0)})
    return results

print("="*60)
print("  尾盘战法 -- 热点板块 vs 传统标的")
print("="*60)

all_data = {}
for label, codes in [("热点板块(14只)", sum(hot_codes.values(),[])),
                      ("传统中小板(10只)", standard)]:
    r = test_codes(label, codes)
    rets = [x["ret"] for x in r]
    avg = np.mean(rets) if rets else 0
    pos = sum(1 for x in rets if x>0)/len(rets)*100 if rets else 0
    all_data[label] = r
    print(f"\n{label}: 有交易{len(r)}/{len(codes)}只")
    print(f"  均收益: {avg:+.2f}%  正收益比: {pos:.0f}%")
    for x in sorted(r, key=lambda x:-x["ret"])[:5]:
        print(f"  {x['code']}: {x['trades']}笔 {x['ret']:+.2f}% WR={x['wr']:.0f}%")

# 板块细分
print("\n" + "="*60)
print("  板块细分")
print("="*60)
for sector, codes in hot_codes.items():
    r = test_codes(sector, codes)
    rets = [x["ret"] for x in r]
    if not rets: continue
    avg = np.mean(rets)
    pos = sum(1 for x in rets if x>0)/len(rets)*100
    print(f"  {sector}: {len(r)}/{len(codes)}只 均收益{avg:+.2f}% 正收益比{pos:.0f}%")

print("\nDone")