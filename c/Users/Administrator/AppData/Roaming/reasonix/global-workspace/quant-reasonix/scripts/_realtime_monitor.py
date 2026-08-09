# -*- coding: utf-8 -*-
"""尾盘战法 — 盘中实时监控系统 v1.0"""
import sys, os, json, time, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd, numpy as np

CACHE = Path(r"C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache")
CONFIG = json.load(open(Path(__file__).parent.parent / "config" / "eod_strategy.json"))

MIN_VR = CONFIG.get("min_vol_ratio", 1.3)
MIN_CP = CONFIG.get("min_close_pos", 0.6)
MAX_PX = CONFIG.get("max_price", 100)

# 交易日判断
def is_trading_day():
    today = datetime.date.today()
    return today.weekday() < 5  # 周一到周五

# 盘中时段判断
def is_market_open():
    now = datetime.datetime.now()
    if now.weekday() >= 5: return False
    t = now.hour * 100 + now.minute
    # 9:25-11:30, 13:00-15:00
    return (925 <= t <= 1130) or (1300 <= t <= 1500)

# 预扫描：开盘前用缓存数据筛选候选池
def prescan_candidates():
    print("开盘前预扫描...")
    files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
                    if f.endswith('.parquet') and not f.startswith('_')
                    and f[:2] in ('00','30','68')])
    candidates = []
    for idx, code in enumerate(files):
        try:
            df = pd.read_parquet(CACHE / f"{code}.parquet")
            col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
            rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
            df = df.rename(columns=rename)
            if 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df = df.set_index('trade_date')
            df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
            if len(df) < 60: continue
        except: continue
        c = df['Close'].values; h = df['High'].values; l = df['Low'].values
        o = df['Open'].values; v = df['Volume'].values; n = len(c); i = n - 1
        if c[i] > MAX_PX: continue
        rng = h[i]-l[i] if h[i]>l[i] else 1
        cp = (c[i]-l[i])/rng
        v5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
        vr = v[i]/v5 if v5>0 else 1
        ma20 = pd.Series(c).rolling(20).mean().values
        if not np.isnan(ma20[i]) and c[i] > ma20[i] and cp >= MIN_CP and vr >= MIN_VR:
            candidates.append(code)
        if (idx+1) % 500 == 0:
            print(f"  预扫描: {idx+1}/{len(files)} 候选={len(candidates)}")
    return candidates

# 盘中实时检查候选
def check_candidates_realtime(candidates):
    from data.fetch.tencent_realtime import get_realtime_quotes
    
    batch_size = 20
    signals = []
    
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        quotes = get_realtime_quotes(batch)
        
        for code in batch:
            q = quotes.get(code)
            if not q: continue
            price = q.get('price', 0)
            if price <= 0: continue
            change_pct = q.get('change_pct', 0)
            volume = q.get('volume', 0)
            
            # 条件检查：价格 <= 100, 当日涨幅 > 0（收阳基础）
            if price <= MAX_PX and change_pct > 0:
                # 开盘价推算收盘位置（近似）
                open_px = q.get('open', price)
                high_px = q.get('high', price)
                low_px = q.get('low', price)
                rng = high_px - low_px if high_px > low_px else 1
                cp = (price - low_px) / rng
                if cp >= MIN_CP:
                    signals.append({
                        'code': code, 'price': price,
                        'change_pct': round(change_pct, 2),
                        'close_pos': round(cp, 2),
                        'volume': volume,
                        'time': q.get('time', ''),
                        'name': q.get('name', code),
                    })
        
        time.sleep(0.3)  # 防封
    
    return signals

def main():
    print("=" * 60)
    print("  尾盘战法 — 盘中实时监控")
    print("=" * 60)
    
    if not is_trading_day():
        print("非交易日，退出")
        return
    
    # 1. 开盘前预扫描
    print(f"\n[1] 预扫描候选池...")
    candidates = prescan_candidates()
    print(f"    候选: {len(candidates)} 只")
    
    if not candidates:
        print("无候选，退出")
        return
    
    # 2. 保存候选
    out = {'date': str(datetime.date.today()), 'time': str(datetime.datetime.now()),
           'candidates': candidates}
    json.dump(out, open(Path(__file__).parent / "daily_data" / 
                        f"candidates_{datetime.date.today()}.json", 'w'),
              ensure_ascii=False, indent=2)
    
    # 3. 盘中循环监控
    print(f"\n[2] 盘中实时监控 (每5分钟扫一次候选)")
    print(f"    候选 {len(candidates)} 只, 每次查询约 {len(candidates)//20+1} 批\n")
    
    last_check = ""
    while is_market_open():
        now = datetime.datetime.now()
        current_minute = f"{now.hour:02d}:{now.minute:02d}"
        
        # 每5分钟检查一次（14:30后每1分钟）
        check_interval = 1 if now.hour >= 14 and now.minute >= 25 else 5
        if current_minute == last_check:
            time.sleep(10)
            continue
        
        last_check = current_minute
        
        if now.minute % check_interval != 0:
            time.sleep(10)
            continue
        
        signals = check_candidates_realtime(candidates)
        
        print(f"\n[{current_minute}] 实时信号: {len(signals)} 只")
        if signals:
            # 按收盘位置排序
            signals.sort(key=lambda x: -x['close_pos'])
            print(f"  {'代码':>8} {'名称':>8} {'现价':>8} {'涨幅%':>7} {'收盘位':>7}")
            print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*7}")
            for s in signals[:10]:
                print(f"  {s['code']:>8} {s['name'][:8]:>8} {s['price']:>8.2f} "
                      f"{s['change_pct']:>+7.2f} {s['close_pos']:>7.2f}")
        
        time.sleep(30)  # 30秒后进入下一个检查周期
    
    print(f"\n[3] 收盘")
    
    # 4. 收盘后保存当日最终信号
    final_signals = check_candidates_realtime(candidates)
    out = {'date': str(datetime.date.today()), 'candidates': len(candidates),
           'final_signals': final_signals[:20]}
    json.dump(out, open(Path(__file__).parent / "daily_data" / 
                        f"realtime_{datetime.date.today()}.json", 'w'),
              ensure_ascii=False, indent=2)
    print(f"收盘保存: {len(final_signals)} 只最终信号")

if __name__ == '__main__':
    main()