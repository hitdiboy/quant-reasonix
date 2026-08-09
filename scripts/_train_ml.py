# ML signal classifier - train from full universe scan
import sys, os, pickle
import pandas as pd, numpy as np

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
         if f.endswith('.parquet') and not f.startswith('_')
         and f[:3] in ('688','002')])

print("Scanning 1401 stocks for signal data...")
all_signals = []
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
    h = df['High'].values; l = df['Low'].values; n = len(c)
    limit_up = 0.198 if code.startswith('688') else 0.098

    streak = np.zeros(n); cnt = 0
    for i in range(1, n):
        if c[i]/c[i-1]-1 >= limit_up: cnt += 1
        else: cnt = 0
        streak[i] = cnt

    for i in range(1, n-5):
        if streak[i-1] >= 2 and c[i] < o[i] and c[i]/c[i-1]-1 < limit_up:
            vol_ma5 = np.mean(v[max(0,i-5):i]) if i >= 5 else np.mean(v[:i])
            vol_r = v[i]/vol_ma5 if vol_ma5 > 0 else 99

            # ATR (14-period)
            if i >= 15:
                tr = np.maximum(h[i-14:i]-l[i-14:i],
                    np.maximum(abs(h[i-14:i]-c[i-15:i-1]),
                              abs(l[i-14:i]-c[i-15:i-1])))
                atr = np.mean(tr)
            else:
                atr = 0
            atr_r = atr/c[i] if c[i] > 0 and atr > 0 else 1

            lc = c[i-int(streak[i-1])-1]
            depth = (c[i]-lc)/lc*100
            is_fake = int(c[i] > c[i-1] and c[i] < o[i])

            ma20 = pd.Series(c).rolling(20).mean().values
            ma20_dev = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
            ret_20d = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i >= 20 else 0

            fwd_ret = (c[i+5]-c[i])/c[i]*100

            all_signals.append({
                'streak': int(streak[i-1]), 'vol_ratio': vol_r,
                'yin_depth': depth, 'atr_ratio': atr_r,
                'is_fake': is_fake, 'ma20_dev': ma20_dev,
                'ret_20d': ret_20d, 'price': c[i],
                'fwd_5d_ret': fwd_ret,
                'is_winner': int(fwd_ret > 3),
            })

    if (idx+1) % 300 == 0:
        sig_cnt = len(all_signals)
        win_cnt = sum(1 for s in all_signals if s['is_winner'])
        print(f'  {idx+1}/{len(files)} signals={sig_cnt} winners={win_cnt}')

print(f'\nTotal signals: {len(all_signals)}')
df = pd.DataFrame(all_signals)
print(f'Winners (>3% fwd_5d): {df["is_winner"].sum()}/{len(df)} ({df["is_winner"].mean()*100:.0f}%)')

# Train
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

features = ['streak','vol_ratio','yin_depth','atr_ratio','is_fake','ma20_dev','ret_20d','price']
X = df[features].fillna(0)
y = df['is_winner']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

model = LogisticRegression(max_iter=1000, C=0.1, class_weight='balanced')
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

print(f'\n=== Model Performance ===')
print(f'Accuracy:  {accuracy_score(y_test, y_pred):.3f}')
print(f'Precision: {precision_score(y_test, y_pred):.3f}')
print(f'Recall:    {recall_score(y_test, y_pred):.3f}')
print(f'F1:        {f1_score(y_test, y_pred):.3f}')

print(f'\n=== Feature Importance ===')
for f, c in sorted(zip(features, model.coef_[0]), key=lambda x: -abs(x[1])):
    print(f'  {f:>12}: {c:+.4f}')

# Best threshold
pred_proba = model.predict_proba(X_test)[:,1]
best_t = 0.5
best_f1 = 0
for t in np.arange(0.3, 0.9, 0.05):
    y_t = (pred_proba >= t).astype(int)
    if y_t.mean() < 0.2: continue
    f1 = f1_score(y_test, y_t)
    if f1 > best_f1:
        best_f1 = f1
        best_t = t

print(f'\n=== Optimal Threshold ===')
print(f'Best threshold: {best_t:.2f} (F1={best_f1:.3f})')
y_opt = (pred_proba >= best_t).astype(int)
print(f'Precision: {precision_score(y_test, y_opt):.3f}')
print(f'Recall:    {recall_score(y_test, y_opt):.3f}')
print(f'Signal acceptance: {y_opt.mean():.1%}')

# Save
os.makedirs('models', exist_ok=True)
pickle.dump({
    'model': model, 'features': features, 'threshold': best_t,
}, open('models/ml_selector.pkl', 'wb'))
print(f'\nModel saved to models/ml_selector.pkl')
print('Done')