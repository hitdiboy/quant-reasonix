# -*- coding: utf-8 -*-
"""赢家 vs 输家 — 深层特征挖掘"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'

# 从全量200只回测中取前50和后50
# 先快速扫描获取所有股票的信号特征
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
         if f.endswith('.parquet') and not f.startswith('_')
         and f[:3] in ('002',)])

print("Scanning stock features...")
stock_features = []
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
        if len(df) < 200: continue
    except: continue

    c = df['Close'].values; o = df['Open'].values; v = df['Volume'].values
    h = df['High'].values; l = df['Low'].values
    n = len(c)
    
    # 20日均线偏离度
    ma20 = pd.Series(c).rolling(20).mean().values
    ma20_dev = (c[-1] - ma20[-1]) / ma20[-1] * 100
    
    # 60日均线偏离度
    ma60 = pd.Series(c).rolling(60).mean().values
    ma60_dev = (c[-1] - ma60[-1]) / ma60[-1] * 100 if not np.isnan(ma60[-1]) else 0
    
    # 近期涨跌幅
    ret_5d = (c[-1] - c[-6]) / c[-6] * 100 if n > 6 else 0
    ret_20d = (c[-1] - c[-21]) / c[-21] * 100 if n > 21 else 0
    
    # 波动率
    daily_ret = np.diff(c) / c[:-1]
    vol_20d = np.std(daily_ret[-20:]) * np.sqrt(252) * 100 if len(daily_ret) >= 20 else 0
    
    # 量比趋势
    vol_ma20 = pd.Series(v).rolling(20).mean().values
    vol_ratio_trend = (v[-1] / vol_ma20[-1]) if vol_ma20[-1] > 0 else 1
    
    # 价格水平
    price = c[-1]
    
    stock_features.append({
        'code': code, 'ma20_dev': ma20_dev, 'ma60_dev': ma60_dev,
        'ret_5d': ret_5d, 'ret_20d': ret_20d, 'vol_20d': vol_20d,
        'vol_ratio': vol_ratio_trend, 'price': price,
    })
    if (idx+1) % 200 == 0:
        print(f'  {idx+1}/{len(files)}')

df_feat = pd.DataFrame(stock_features)
print(f'\nTotal stocks scanned: {len(df_feat)}')

# 看赢家/输家在这些特征上的差异
# 根据 ret_20d 分组（近期涨幅大的可能是赢家）
df_feat['ret_20d_pctile'] = pd.qcut(df_feat['ret_20d'], 5, labels=['Q1(最低)', 'Q2', 'Q3', 'Q4', 'Q5(最高)'], duplicates='drop')
print(f'\n分组统计（按 ret_20d）：')
print(df_feat.groupby('ret_20d_pctile', observed=False).agg({
    'ma20_dev': 'mean', 'ma60_dev': 'mean', 'vol_20d': 'mean',
    'vol_ratio': 'mean', 'price': 'mean', 'code': 'count'
}).round(2))

# 信号预测质量
print(f'\n最关键的发现：')
print(f'  - 20日均线偏离度: 均值为 {df_feat["ma20_dev"].mean():+.2f}%')
print(f'  - 高位股(ma20>20%)占比: {(df_feat["ma20_dev"] > 20).mean()*100:.1f}%')
print(f'  - 低位股(ma20<-20%)占比: {(df_feat["ma20_dev"] < -20).mean()*100:.1f}%')
print(f'\n建议筛选规则：')
print(f'  - 信号当日收盘价在 MA20 上方（多头排列）')
print(f'  - 近20日涨幅为正（趋势向上）')
print(f'  - 20日波动率 > 40%（有足够弹性）')
print('Done')