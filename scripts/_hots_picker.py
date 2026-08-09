# -*- coding: utf-8 -*-
"""a-stock-data 集成：热点选股 + 资金流 + 涨停池 + 信号融合"""
import sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从 SKILL.md 提取核心函数
import requests as _rq, pandas as pd, numpy as np
from pathlib import Path

# ---------- a-stock-data 核心函数 (直接嵌入) ----------
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"
CN_TZ = datetime.timezone(datetime.timedelta(hours=8))
def cn_today(): return datetime.datetime.now(CN_TZ).date().isoformat()

def _em_get(url, params=None, headers=None, timeout=15):
    if headers is None: headers = {"User-Agent": UA}
    try:
        return _rq.get(url, params=params, headers=headers, timeout=timeout)
    except Exception as e:
        return type("R", (), {"json": lambda self: {"data": {"diff": [], "total": 0}}})()

def ths_hot_reason(date=None):
    """同花顺热点强势股归因"""
    if date is None: date = cn_today()
    url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{date}/orderby/date/orderway/desc/charset/GBK/"
    try:
        r = _rq.get(url, headers={"User-Agent": UA}, timeout=10)
        data = r.json()
        rows = (data.get("data") or []) if data.get("errocode", 0) == 0 else []
    except: rows = []
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={"name": "名称", "code": "代码", "reason": "题材归因",
                             "close": "收盘价", "zhangfu": "涨幅%", "huanshou": "换手率%",
                             "chengjiaoe": "成交额", "ddejingliang": "大单净量", "market": "市场"})
    return df

def ths_limit_up_pool(date=None):
    """同花顺涨停池(涨停原因+封板质量)"""
    if date is None: date = cn_today().replace("-", "")
    url = "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
    params = {"page": 1, "limit": 200,
              "field": "199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004",
              "filter": "HS,GEM2STAR", "order_field": "330324", "order_type": "0", "date": date}
    try:
        r = _rq.get(url, params=params, headers={"User-Agent": UA}, timeout=10)
        info = (r.json().get("data") or {}).get("info", [])
    except: info = []
    out = []
    for it in info:
        ft = it.get("first_limit_up_time")
        out.append({"code": it.get("code"), "name": it.get("name"), "price": it.get("latest"),
            "pct": it.get("change_rate"), "reason": it.get("reason_type", ""),
            "board_type": it.get("limit_up_type", ""), "seal_rate": it.get("limit_up_suc_rate"),
            "break_times": it.get("open_num") or 0, "seal_amount": it.get("order_amount"),
            "high_days": it.get("high_days", ""),
            "first_time": datetime.datetime.fromtimestamp(int(ft)).strftime("%H:%M:%S") if ft else "",
            "is_again": it.get("is_again_limit")})
    return out

def industry_comparison(top_n=20):
    """行业板块涨跌幅排名"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {"pn": "1", "pz": "100", "po": "1", "np": "1", "fltt": "2", "invt": "2",
              "fid": "f3", "fs": "m:90+t:2",
              "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207"}
    try:
        r = _em_get(url, params=params)
        items = r.json().get("data", {}).get("diff", [])
    except: items = []
    rows = [{"rank": i+1, "name": it.get("f14",""), "change_pct": it.get("f3",0),
             "code": it.get("f12",""), "up_count": it.get("f104",0), "down_count": it.get("f105",0),
             "leader": it.get("f140",""), "leader_change": it.get("f136",0)}
            for i, it in enumerate(items)]
    return {"top": rows[:top_n], "bottom": rows[-top_n:], "total": len(rows)}

def board_fund_flow(board_type="industry", period="today", top_n=20):
    """板块资金流向排名"""
    _BOARD_FS = {"industry": "m:90+t:2", "concept": "m:90+t:3", "region": "m:90+t:1"}
    _BP = {"today": ("f62","f62","f84","f3","f128"), "5d": ("f107","f107","f108","f104",""),
           "10d": ("f166","f166","f167","f108","")}
    if board_type not in _BOARD_FS: return {"rows":[]}
    fid, f_main, f_pct, f_chg, f_ld = _BP.get(period, _BP["today"])
    fields = ["f12","f14",f_chg,f_main,f_pct]
    if f_ld: fields.append(f_ld)
    if period == "today": fields += ["f66","f72","f78","f84"]
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {"pz":"200","po":"1","np":"1","fltt":"2","invt":"2","fid":fid,
              "fs":_BOARD_FS[board_type],"fields":",".join(dict.fromkeys(fields))}
    try:
        r = _em_get(url, params=params)
        items = r.json().get("data",{}).get("diff",[])
    except: items = []
    rows = []
    for i, it in enumerate(items):
        row = {"rank":i+1,"name":it.get("f14",""),"code":it.get("f12",""),
               "change_pct":it.get(f_chg,0),"main_net":it.get(f_main,0),
               "main_pct":it.get(f_pct,0),"leader":it.get(f_ld,"") if f_ld else ""}
        if period == "today":
            row.update({"super_net":it.get("f66",0),"large_net":it.get("f72",0),
                        "medium_net":it.get("f78",0),"small_net":it.get("f84",0)})
        rows.append(row)
    return {"board_type":board_type,"period":period,"total":len(rows),"rows":rows[:top_n]}

# ========== 核心集成：热点选股 ==========
def hot_stock_picker(min_score=60, top_n=5):
    """融合热点+资金+涨停的选股引擎"""
    today = cn_today()
    report = {"date": today, "sectors": [], "limit_up_stocks": [], "fund_flow": [],
              "picks": [], "signals": []}
    
    # 1. 行业板块排名
    ind = industry_comparison(10)
    report["sectors"] = [{"name": r["name"], "pct": r["change_pct"],
                          "leader": r.get("leader",""), "leader_pct": r.get("leader_change",0)}
                         for r in ind.get("top",[])]
    
    # 2. 板块资金流向
    bf = board_fund_flow("industry", "today", 10)
    report["fund_flow"] = [{"name": r["name"], "main_net": round(r["main_net"]/1e8,2),
                            "main_pct": r["main_pct"], "leader": r.get("leader","")}
                           for r in bf.get("rows",[])]
    
    # 3. 涨停池
    zt = ths_limit_up_pool(today.replace("-",""))
    report["limit_up_stocks"] = [{"code": s["code"], "name": s["name"], "pct": s["pct"],
                                   "reason": s["reason"], "board_type": s["board_type"],
                                   "high_days": s["high_days"], "seal_rate": s["seal_rate"],
                                   "break_times": s["break_times"]}
                                  for s in zt[:20]]
    
    # 4. 同花顺热点归因
    hr = ths_hot_reason(today)
    
    # 5. 融合选股：涨停池中筛选高质量标的
    candidates = []
    for s in zt:
        # 加分项
        score = 50
        if s["seal_rate"] and s["seal_rate"] >= 0.7: score += 15  # 封板率高
        if s["break_times"] == 0: score += 10                       # 未炸板
        if s["board_type"] in ("一字板", "T字板"): score += 5        # 强势封板形态
        if s["reason"]: score += 5                                  # 有题材归因
        if score >= min_score:
            candidates.append({"code": s["code"], "name": s["name"], "pct": s["pct"],
                                "reason": s["reason"], "high_days": s["high_days"],
                                "score": score, "seal_rate": s["seal_rate"]})
    
    candidates.sort(key=lambda x: -x["score"])
    report["picks"] = candidates[:top_n]
    
    # 6. 尾盘/龙首阴信号标注 (从涨停池看连板+首阴潜力)
    signals = []
    for s in zt:
        hd = s.get("high_days","")
        if hd and "连" in str(hd):
            signals.append({"code": s["code"], "name": s["name"], "high_days": hd,
                            "reason": s["reason"], "source": "连板跟踪"})
    report["signals"] = signals[:5]
    
    return report


def print_report(report):
    print(f"\n{'='*60}")
    print(f"  a-stock-data 热点选股系统")
    print(f"  {report['date']}")
    print(f"{'='*60}")
    
    # 行业TOP10
    print(f"\n[行业板块 TOP10]")
    for s in report["sectors"][:10]:
        ld = f" 领涨{s['leader']}" if s.get("leader") else ""
        print(f"  {s['name']:>10s}: {s['pct']:+.2f}%{ld}")
    
    # 资金流TOP10
    print(f"\n[板块资金流入 TOP10]")
    for f in report["fund_flow"][:10]:
        ld = f" 领涨{f.get('leader','')}" if f.get("leader") else ""
        print(f"  {f['name']:>10s}: 主力净流入{f['main_net']:.2f}亿 ({f['main_pct']}%){ld}")
    
    # 涨停池
    print(f"\n[今日涨停池 ({len(report['limit_up_stocks'])}只)]")
    for s in report["limit_up_stocks"][:10]:
        print(f"  {s['code']} {s['name']:>8s} {s['pct']:+.2f}% {s['reason'][:30]:30s} "
              f"{s['high_days']} {s['board_type']} 封板率{s['seal_rate']}")
    
    # 精选
    print(f"\n[TOP{len(report['picks'])} 精选]")
    for s in report["picks"]:
        print(f"  {s['code']} {s['name']:>8s} 评分{s['score']} {s['reason'][:40]:40s} {s['high_days']}")
    
    # 连板信号
    if report["signals"]:
        print(f"\n[连板跟踪信号]")
        for s in report["signals"]:
            print(f"  {s['code']} {s['name']:>8s} {s['high_days']} {s['reason'][:40]}")
    
    print(f"\n{'='*60}")
    print(f"  a-stock-data | 数据来源: 同花顺/东财/腾讯")
    print(f"{'='*60}")


if __name__ == "__main__":
    report = hot_stock_picker()
    print_report(report)
    
    # 保存
    out_path = Path(__file__).parent / "daily_data" / f"hots_{cn_today()}.json"
    out_path.parent.mkdir(exist_ok=True)
    # 清理不可JSON序列化的类型
    def clean(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.ndarray,)): return obj.tolist()
        if isinstance(obj, pd.DataFrame): return obj.to_dict(orient="records")
        return obj
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=clean)
    print(f"\n已保存: {out_path}")