# -*- coding: utf-8 -*-
"""ML选股模型 — 用全量回测数据训练信号评分分类器"""
import sys, os, json, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np
from backtesting import Backtest
from strategies.custom.strategy_004_dragon_first_yin_v38 import DragonFirstYinV38
from engine.factors.dragon_selector import compute_dragon_factors, calc_signal_score

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
         if f.endswith('.parquet') and not f.startswith('_')
         and f[:3] in ('688','002')])

# Step 1: Scan and collect features + returns at each signal point
print("Step 1: Scanning 1401 stocks for signal data...")
signals_data = []
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
    
    # Calculate streak
    limit_up = 0.198 if code.startswith('688') else 0.098
    streak = np.zeros(n); cnt = 0
    for i in range(1, n):
        if c[i]/c[i-1]-1 >= limit_up: cnt += 1
        else: cnt = 0
        streak[i] = cnt
    
    # Calculate factors once for this stock
    factors = compute_dragon_factors(c, h, l, o, v)
    if not factors: continue
    
    # For each signal point, collect features
    for i in range(1, n-5):
        if streak[i-1] >= 2 and c[i] < o[i] and c[i]/c[i-1]-1 < limit_up:
            # Signal features
            vol_ma5 = np.mean(v[max(0,i-5):i])
            vol_ratio = v[i] / vol_ma5 if vol_ma5 > 0 else 99
            atr = np.mean(np.maximum(h[max(0,i-14):i]-l[max(0,i-14):i],
                           np.maximum(abs(h[max(0,i-14):i]-c[max(1,i-14):i]),
                                      abs(l[max(0,i-14):i]-c[max(1,i-14):i])))) if i >= 14 else 0
            atr_ratio = atr / c[i] if c[i] > 0 and atr > 0 else 1
            
            limit_close = c[i-int(streak[i-1])-1]
            yin_depth = (c[i] - limit_close) / limit_close * 100
            
            is_fake = c[i] > c[i-1] and c[i] < o[i]
            
            # Forward return (5-day)
            fwd_ret = (c[i+5] - c[i]) / c[i] * 100
            
            # Factor scores at signal point
            alpha56 = factors['alpha056'][i]
            alpha95 = factors['alpha095'][i]
            alpha151 = factors['alpha151'][i]
            alpha15 = factors['alpha015'][i]
            
            signals_data.append({
                'code': code, 'date': str(df.index[i].date()),
                'streak': int(streak[i-1]),
                'vol_ratio': vol_ratio, 'yin_depth': yin_depth,
                'atr_ratio': atr_ratio, 'is_fake': int(is_fake),
                'alpha056': alpha56 if not np.isnan(alpha56) else 0.5,
                'alpha095': alpha95 if not np.isnan(alpha95) else 0.5,
                'alpha151': alpha151 if not np.isnan(alpha151) else 0,
                'alpha015': alpha15 if not np.isnan(alpha15) else 0,
                'fwd_5d_ret': fwd_ret,
                'is_winner': int(fwd_ret > 0),
                'price': c[i],
            })
    
    if (idx+1) % 200 == 0:
        print(f'  {idx+1}/{len(files)} signals={len(signals_data)}')

print(f'\nTotal signal points collected: {len(signals_data)}')
print(f'Winners (fwd_5d>0): {sum(1 for s in signals_data if s[\"is_winner\"])} ({sum(1 for s in signals_data if s[\"is_winner\"])/len(signals_data)*100:.0f}%)')

# Step 2: Train a simple logistic regression model
print('\nStep 2: Training ML model...')
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score

df_sig = pd.DataFrame(signals_data)

features = ['streak', 'vol_ratio', 'yin_depth', 'atr_ratio', 'is_fake',
            'alpha056', 'alpha095', 'alpha151', 'alpha015']
X = df_sig[features].fillna(0.5)
y = df_sig['is_winner']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

model = LogisticRegression(max_iter=1000, C=0.1, class_weight='balanced')
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print(f'Accuracy:  {accuracy_score(y_test, y_pred):.3f}')
print(f'Precision: {precision_score(y_test, y_pred):.3f}')
print(f'Recall:    {recall_score(y_test, y_pred):.3f}')
print(f'Signal rate: {y_pred.mean():.3f} (would take {y_pred.mean()*100:.0f}% of signals)')

# Feature importance (coefficients)
coef_df = pd.DataFrame({'feature': features, 'coef': model.coef_[0]})
coef_df = coef_df.sort_values('coef', key=abs, ascending=False)
print('\nFeature importance (by absolute coefficient):')
for _, r in coef_df.iterrows():
    print(f'  {r[\"feature\"]:>12}: {r[\"coef\"]:+.4f}')

# Step 3: Save model
os.makedirs('models', exist_ok=True)
with open('models/signal_classifier.pkl', 'wb') as f:
    pickle.dump({'model': model, 'features': features}, f)
print(f'\nModel saved to models/signal_classifier.pkl')

# Step 4: Analyze what the model considers important
print('\nStep 3: Model insights for strategy improvement')
pred_proba = model.predict_proba(X_test)[:, 1]
# Optimal threshold search
best_threshold = 0.5
best_precision = 0
for thresh in np.arange(0.3, 0.9, 0.05):
    y_pred_t = (pred_proba >= thresh).astype(int)
    prec = precision_score(y_test, y_pred_t)
    rec = recall_score(y_test, y_pred_t)
    signal_rate = y_pred_t.mean()
    if prec > best_precision and signal_rate > 0.2:  # at least 20% of signals
        best_threshold = thresh
        best_precision = prec

print(f'Optimal threshold: {best_threshold:.2f}')
print(f'At threshold {best_threshold:.2f}:')
y_pred_opt = (pred_proba >= best_threshold).astype(int)
print(f'  Precision: {precision_score(y_test, y_pred_opt):.3f}')
print(f'  Recall: {recall_score(y_test, y_pred_opt):.3f}')
print(f'  Signal rate: {y_pred_opt.mean():.3f}')

# Save threshold
with open('models/signal_classifier.pkl', 'wb') as f:
    pickle.dump({'model': model, 'features': features, 'threshold': best_threshold}, f)
print('Model with optimal threshold saved.')
print('Done')