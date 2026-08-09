# -*- coding: utf-8 -*-
import sys, os, json, datetime, requests as _rq, re as _re
from pathlib import Path
import pandas as pd
import numpy as np

# 指向 quant-codex 的缓存（数据在那儿）
ROOT = Path(r"C:\Users\Administrator\Codex-Workspace\quant-codex")
CACHE_DIR = ROOT / "data" / "cache"
CACHE_CN_DIR = ROOT / "data" / "cache" / "cn"
PAPER_DIR = Path(__file__).parent
SIGNALS_FILE = PAPER_DIR / "dragon_signals.json"
POSITIONS_FILE = PAPER_DIR / "dragon_positions.json"
ALLOWED = ("300", "002", "688")

def get_stock_list():
    codes = []
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".parquet"):
            c = f.replace(".parquet", "")
            if c.startswith(ALLOWED):
                codes.append(c)
    return sorted(codes)

def read_from_cache_v2(code):
    for base in [CACHE_DIR, CACHE_CN_DIR]:
        path = base / f"{code}.parquet"
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if df is None or len(df) == 0:
                    continue
                df = df.copy()
                date_cols = [c for c in df.columns if c.lower().strip() in ("trade_date","date","datetime")]
                if date_cols:
                    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                    df = df.set_index(date_cols[0]).sort_index()
                df.index.name = "Date"
                rename = {}
                for c in df.columns:
                    cl = c.lower().strip()
                    if cl == "open": rename[c] = "Open"
                    elif cl == "high": rename[c] = "High"
                    elif cl == "low": rename[c] = "Low"
                    elif cl == "close": rename[c] = "Close"
                    elif cl in ("volume","vol"): rename[c] = "Volume"
                df = df.rename(columns=rename)
                std_cols = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
                df = df[std_cols].ffill().bfill().dropna()
                return df if len(df) >= 30 else None
            except:
                continue
    return None

def read_from_cache(code):
    path = CACHE_DIR / f"{code}.parquet"
    if not path.exists():
        return read_from_cache_v2(code)
    try:
        df = pd.read_parquet(path)
        if df is None or len(df) == 0:
            return read_from_cache_v2(code)
        df = df.copy()
        date_cols = [c for c in df.columns if c.lower().strip() in ("trade_date","date","datetime")]
        if date_cols:
            df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
            df = df.set_index(date_cols[0]).sort_index()
        df.index.name = "Date"
        rename = {}
        for c in df.columns:
            cl = c.lower().strip()
            if cl == "open": rename[c] = "Open"
            elif cl == "high": rename[c] = "High"
            elif cl == "low": rename[c] = "Low"
            elif cl == "close": rename[c] = "Close"
            elif cl in ("volume","vol"): rename[c] = "Volume"
        df = df.rename(columns=rename)
        std_cols = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
        df = df[std_cols].ffill().bfill().dropna()
        return df if len(df) >= 30 else None
    except:
        return read_from_cache_v2(code)

def detect(df):
    if df is None or len(df) < 15:
        return False, 0, {}
    close = df["Close"].values; high = df["High"].values; low = df["Low"].values
    volume = df["Volume"].values; n = len(close)
    tr = np.max([high[1:]-low[1:], np.abs(high[1:]-close[:-1]), np.abs(low[1:]-close[:-1])], axis=0)
    atr = np.mean(tr[-14:]) if len(tr)>=14 else np.mean(tr)
    atr_r = atr/close[-1] if close[-1]>0 else 0
    vol_ma5 = np.mean(volume[-5:]) if n>=5 else np.mean(volume)
    if n < 3: return False, 0, {}
    limit_ups = 0
    for i in range(max(0,n-10), n):
        if i>0 and close[i]>=close[i-1]*1.098: limit_ups += 1
    if limit_ups < 2: return False, 0, {}
    is_yin = df["Close"].iloc[-1] < df["Open"].iloc[-1]
    if not is_yin: return False, 0, {}
    prev_c = close[-2] if n>=2 else close[-1]
    yin_pct = (close[-1]-prev_c)/prev_c*100
    vol_r = volume[-1]/vol_ma5 if vol_ma5>0 else 999
    score = 50
    if limit_ups>=3: score+=15
    elif limit_ups>=2: score+=5
    if vol_r<=1.0: score+=15
    elif vol_r<=1.5: score+=8
    if yin_pct>=-1.0: score+=10
    elif yin_pct>=-2.0: score+=5
    if atr_r<=0.10: score+=10
    elif atr_r<=0.15: score+=5
    score = min(100, max(0, score))
    d = {"limit_ups":limit_ups,"is_yin":is_yin,"yin_pct":round(yin_pct,2),
         "vol_ratio":round(vol_r,2),"atr_ratio":round(atr_r,4),"score":score,
         "close":round(close[-1],2),"volume":int(volume[-1]),"date":str(df.index[-1].date())}
    return True, score, d

def load_signals():
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE,"r",encoding="utf-8") as f: return json.load(f)
    return []

def save_signals(sig):
    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SIGNALS_FILE,"w",encoding="utf-8") as f: json.dump(sig,f,ensure_ascii=False,indent=2)

def load_positions():
    if POSITIONS_FILE.exists():
        with open(POSITIONS_FILE,"r",encoding="utf-8") as f: return json.load(f)
    return {}

def save_positions(pos):
    POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSITIONS_FILE,"w",encoding="utf-8") as f: json.dump(pos,f,ensure_ascii=False,indent=2)

def calc_size(score, total=1000000):
    if score>=80: return int(total*0.15)
    elif score>=65: return int(total*0.12)
    elif score>=50: return int(total*0.10)
    else: return int(total*0.05)

def auto_buy(code, detail, positions, signals, buy_price=None):
    today = str(datetime.date.today())
    if code in positions: return False, "已持仓"
    for sig in signals:
        if sig["code"]==code and sig.get("status") in ("signal","buy"): return False, "已有未完成信号"
    score = detail["score"]; price = buy_price or detail["close"]
    amt = calc_size(score, 1000000)
    shares = int(amt/price/100)*100
    if shares < 100: return False, "金额不足100股"
    sig = {"code":code,"date":today,"score":score,"price":price,"shares":shares,
           "amount":round(shares*price,2),"limit_ups":detail["limit_ups"],
           "yin_pct":detail["yin_pct"],"vol_ratio":detail["vol_ratio"],
           "atr_ratio":detail["atr_ratio"],"status":"buy","entry_date":today,"entry_price":price}
    signals.append(sig); save_signals(signals)
    positions[code] = {"entry_date":today,"entry_price":price,"shares":shares,
                       "current_price":price,"highest_price":price,"score":score,"bars_held":0}
    save_positions(positions)
    return True, f"买入 {shares}股 @ {price}"

def confirm_signal(code, signal_date, signal_price, signal_volume):
    try:
        df = read_from_cache(code)
        if df is None or len(df) < 3:
            return False, None, "数据不足"
        sd = pd.to_datetime(signal_date)
        idx = df.index.get_indexer([sd], method='pad')[0]
        if idx >= len(df) - 1:
            return False, None, "无后续交易日"
        cr = df.iloc[idx + 1]
        cc = float(cr["Close"]); cv = float(cr["Volume"])
        vr = cv / signal_volume if signal_volume > 0 else 999
        pr = cc / signal_price
        reasons = []
        if vr > 1.3: reasons.append(f"放量({vr:.2f}x)")
        if pr < 0.97: reasons.append(f"续跌({pr:.2%})")
        if reasons: return False, None, "; ".join(reasons)
        return True, {"date":str(df.index[idx+1].date()),"close":cc,"volume":int(cv),"vol_ratio":round(vr,2),"price_ratio":round(pr,4)}, ""
    except Exception as e:
        return False, None, str(e)

def _fetch_realtime_prices(codes):
    if not codes:
        return {}
    for k in list(os.environ.keys()):
        if k.lower().endswith('_proxy') or k.lower() == 'no_proxy':
            os.environ.pop(k, None)
    batch_size = 20
    results = {}
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        tencodes = [('sh' + c) if c.startswith('6') else ('sz' + c) for c in batch]
        url = 'http://qt.gtimg.cn/q=' + ','.join(tencodes)
        try:
            r = _rq.get(url, timeout=10)
            r.encoding = 'gbk'
            text = r.text
        except Exception as e:
            print('  Tencent quote failed: ' + str(e))
            continue
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line or not line.startswith('v_'): continue
            m = _re.match(r'v_\w+="(.+)"', line)
            if not m: continue
            parts = m.group(1).split('~')
            if len(parts) < 35: continue
            code = parts[2]
            try:
                results[code] = float(parts[3]) if parts[3] else 0
            except: continue
    return results

def update_positions_realtime(positions):
    today = datetime.date.today()
    codes = list(positions.keys())
    if not codes:
        return []
    print('  Getting realtime quotes for ' + str(len(codes)) + ' stocks...', flush=True)
    prices = _fetch_realtime_prices(codes)
    if not prices:
        print('  Realtime failed, falling back to cache')
        return update_positions(positions)
    to_remove = []
    hit = 0
    for code, pos in positions.items():
        cur = prices.get(code)
        if cur is None or cur == 0:
            continue
        hit += 1
        pos['current_price'] = cur
        pos['highest_price'] = max(pos.get('highest_price', 0), cur)
        ed = datetime.datetime.strptime(pos['entry_date'], '%Y-%m-%d').date()
        pos['bars_held'] = (today - ed).days
        ep = pos['entry_price']
        hp = pos['highest_price']
        pnl = (cur - ep) / ep * 100
        if hp > ep:
            dd = (hp - cur) / hp * 100
            if dd >= 4.0:
                pos['exit_reason'] = '移动止损'
                to_remove.append(code)
                continue
        if pnl <= -8.0:
            pos['exit_reason'] = '硬止损'
            to_remove.append(code)
            continue
        if pos['bars_held'] >= 10:
            pos['exit_reason'] = '时间止损'
            to_remove.append(code)
            continue
    print('  Realtime update: ' + str(hit) + '/' + str(len(codes)) + ' ok, ' + str(len(to_remove)) + ' exited', flush=True)
    for code in to_remove:
        pos = positions.pop(code)
        pos['exit_date'] = str(today)
        signals = load_signals()
        for sig in signals:
            if sig['code'] == code and sig.get('status') in ('buy', 'tracking'):
                sig['status'] = 'closed'
                sig['exit_date'] = str(today)
                sig['exit_price'] = pos['current_price']
                sig['exit_reason'] = pos.get('exit_reason', '未知')
                sig['pnl_pct'] = round((pos['current_price'] - pos['entry_price']) / pos['entry_price'] * 100, 2)
                break
        save_signals(signals)
    save_positions(positions)
    return to_remove

def update_positions(positions):
    today = datetime.date.today(); to_remove = []
    for code, pos in positions.items():
        df = read_from_cache(code)
        if df is None or len(df)==0: continue
        cur = float(df["Close"].iloc[-1])
        pos["current_price"] = cur
        pos["highest_price"] = max(pos.get("highest_price",0), cur)
        ed = datetime.datetime.strptime(pos["entry_date"],"%Y-%m-%d").date()
        pos["bars_held"] = (today-ed).days
        ep = pos["entry_price"]; hp = pos["highest_price"]
        pnl = (cur-ep)/ep*100
        if hp > ep:
            dd = (hp-cur)/hp*100
            if dd >= 4.0: pos["exit_reason"]="移动止损"; to_remove.append(code); continue
        if pnl <= -8.0: pos["exit_reason"]="硬止损"; to_remove.append(code); continue
        if pos["bars_held"] >= 10: pos["exit_reason"]="时间止损"; to_remove.append(code); continue
    for code in to_remove:
        pos = positions.pop(code); pos["exit_date"]=str(today)
        signals = load_signals()
        for sig in signals:
            if sig["code"]==code and sig.get("status") in ("buy","tracking"):
                sig["status"]="closed"; sig["exit_date"]=str(today)
                sig["exit_price"]=pos["current_price"]
                sig["exit_reason"]=pos.get("exit_reason","未知")
                sig["pnl_pct"]=round((pos["current_price"]-pos["entry_price"])/pos["entry_price"]*100,2)
                break
        save_signals(signals)
    save_positions(positions)
    return to_remove

def print_report(signals, positions, new_signals=None):
    today = str(datetime.date.today())
    print("="*60); print(f"  龙首阴监控报告 -- {today}"); print("="*60)
    print("\n> 今日新信号:")
    if new_signals:
        print(f"  {'代码':>8} {'评分':>5} {'涨跌幅':>7} {'量比':>6} {'ATR':>6} {'价格':>8}")
        print(f"  {'-'*8} {'-'*5} {'-'*7} {'-'*6} {'-'*6} {'-'*8}")
        for s in new_signals:
            print(f"  {s['code']:>8} {s['score']:>5} {s['yin_pct']:>7} {s['vol_ratio']:>6} {s['atr_ratio']:>6} {s['close']:>8}")
    else: print("  无")
    print("\n> 当前持仓:")
    if positions:
        print(f"  {'代码':>8} {'天数':>5} {'入价':>8} {'现价':>8} {'收益%':>7} {'最高':>8}")
        print(f"  {'-'*8} {'-'*5} {'-'*8} {'-'*8} {'-'*7} {'-'*8}")
        for code, pos in sorted(positions.items()):
            pnl = (pos["current_price"]-pos["entry_price"])/pos["entry_price"]*100
            print(f"  {code:>8} {pos['bars_held']:>5} {pos['entry_price']:>8.2f} {pos['current_price']:>8.2f} {pnl:>+7.2f} {pos['highest_price']:>8.2f}")
    else: print("  空仓")
    active = [s for s in signals if s.get("status") in ("signal","buy","tracking")]
    closed = [s for s in signals if s.get("status")=="closed"]
    print(f"\n> 汇总: 总信号 {len(signals)} | 进行中 {len(active)} | 已平仓 {len(closed)}")
    if closed:
        wins = [s for s in closed if s.get("pnl_pct",0)>0]
        loss = [s for s in closed if s.get("pnl_pct",0)<=0]
        avg = np.mean([s.get("pnl_pct",0) for s in closed]) if closed else 0
        print(f"  盈利 {len(wins)}笔 | 亏损 {len(loss)}笔 | 平均盈亏 {avg:+.2f}%")
    print()

def main():
    mode = "scan"
    if len(sys.argv)>1 and sys.argv[1]=="--track": mode="track"
    if len(sys.argv)>1 and sys.argv[1]=="--realtime": mode="realtime"
    if len(sys.argv)>2:
        if sys.argv[2]=="--track": mode="track"
        if sys.argv[2]=="--realtime": mode="realtime"
        if sys.argv[2]=="--scan": mode="scan"
    print(f"龙首阴监控 -- 模式: {mode}")
    signals = load_signals(); positions = load_positions()
    if mode=="track":
        exited = update_positions(positions)
        if exited: print(f"  今日出场: {', '.join(exited)}")
        print_report(signals, positions); return
    if mode=="realtime":
        exited = update_positions_realtime(positions)
        if exited: print(f"  今日出场: {', '.join(exited)}")
        signals = load_signals()
        print_report(signals, positions); return
    codes = get_stock_list()
    print(f"扫描范围: {len(codes)} 只 (创小科)"); new_sigs=[]; errors=[]
    for i, code in enumerate(codes):
        if (i+1)%500==0: print(f"  进度: {i+1}/{len(codes)}", flush=True)
        try:
            df = read_from_cache(code)
            ok, score, detail = detect(df)
            if ok and score>=50:
                detail["code"]=code; new_sigs.append(detail)
                ok2, msg = auto_buy(code, detail, positions, signals)
                if ok2: print(f"  [OK] {code} 评分{score} -> {msg}", flush=True)
                else: print(f"  [!]  {code} 评分{score} -> {msg}", flush=True)
        except Exception as e: errors.append((code,str(e)))
    print(f"\n扫描完成: {len(new_sigs)} 个新信号, {len(errors)} 个错误")
    if errors:
        print("\n错误详情 (最多5条):")
        for c,e in errors[:5]: print(f"  {c}: {e}")
    print_report(signals, positions, new_sigs)

if __name__=="__main__": main()
# ---- ML 选股评分集成 ----
import pickle as _pk
_ML_DIR = Path(__file__).parent.parent / "models"
_ML_MODEL_PATH = _ML_DIR / "ml_selector.pkl"
_ml_model = None
_ml_features = None
_ml_threshold = None

def _load_ml_model():
    global _ml_model, _ml_features, _ml_threshold
    if _ML_MODEL_PATH.exists():
        try:
            data = _pk.load(open(_ML_MODEL_PATH, 'rb'))
            if isinstance(data, dict):
                _ml_model = data.get('model')
                _ml_features = data.get('features')
                _ml_threshold = data.get('threshold', 0.4)
            else:
                _ml_model = data
                _ml_features = ['streak','vol_ratio','yin_depth','atr_ratio','is_fake','ma20_dev','ret_20d','price']
                _ml_threshold = 0.4
            return True
        except: pass
    return False

def calc_ml_score(code, detail):
    """用ML模型计算信号评分 (0-100)"""
    if _ml_model is None:
        if not _load_ml_model():
            return detail.get('score', 50)
    try:
        df = read_from_cache(code)
        if df is None or len(df) < 30: return detail.get('score', 50)
        c = df['Close'].values; o = df['Open'].values; v = df['Volume'].values
        h = df['High'].values; l = df['Low'].values; n = len(c)
        i = n - 1
        # 计算特征
        limit_up = 0.198 if code.startswith(('300','688')) else 0.098
        streak_cnt = 0
        for j in range(max(0,i-10), i):
            if j>0 and c[j]/c[j-1]-1 >= limit_up: streak_cnt += 1
            else: streak_cnt = 0
        
        vol_ma5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
        vol_r = v[i]/vol_ma5 if vol_ma5>0 else 99
        
        if i >= 15:
            tr = np.maximum(h[i-14:i]-l[i-14:i],
                np.maximum(abs(h[i-14:i]-c[i-15:i-1]),
                          abs(l[i-14:i]-c[i-15:i-1])))
            atr = np.mean(tr)
        else: atr = 0
        atr_r = atr/c[i] if c[i]>0 and atr>0 else 1
        
        lc = c[i-int(streak_cnt)-1] if streak_cnt>=1 else c[i-1]
        depth = (c[i]-lc)/lc*100
        is_fake = int(c[i] > c[i-1] and c[i] < o[i])
        
        ma20 = pd.Series(c).rolling(20).mean().values
        ma20_dev = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
        ret_20d = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0
        
        # 构建特征向量
        feat = np.array([[streak_cnt, vol_r, depth, atr_r, is_fake, ma20_dev, ret_20d, c[i]]])
        feat_df = pd.DataFrame(feat, columns=_ml_features).fillna(0)
        
        proba = _ml_model.predict_proba(feat_df)[0, 1]
        ml_score = int(proba * 100)
        return ml_score
    except:
        return detail.get('score', 50)

# 覆盖 auto_buy 使用 ML 评分
_original_auto_buy = auto_buy
def auto_buy(code, detail, positions, signals, buy_price=None):
    ml_score = calc_ml_score(code, detail)
    detail['ml_score'] = ml_score
    # 如果 ML 评分低于阈值则不买
    if ml_score < 35:  # 对应概率 < 35%
        return False, f"ML评分{ml_score}低于阈值"
    return _original_auto_buy(code, detail, positions, signals, buy_price)
