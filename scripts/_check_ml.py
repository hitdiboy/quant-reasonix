import pickle, pandas as pd, numpy as np

data = pickle.load(open('models/ml_selector.pkl', 'rb'))
model = data['model']
features = data['features']
threshold = data.get('threshold', 0.4)
print('ML features:', features)
print('Threshold:', threshold)

df = pd.read_parquet('C:/Users/Administrator/Codex-Workspace/quant-codex/data/cache/002432.parquet')
col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
df = df.rename(columns=rename)
if 'trade_date' in df.columns:
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.set_index('trade_date')
df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()

c = df['Close'].values; o = df['Open'].values; v = df['Volume'].values
h = df['High'].values; l = df['Low'].values; n = len(c); i = n - 1

limit_up = 0.098
streak = 0
for j in range(max(0,i-10), i):
    if j>0 and c[j]/c[j-1]-1 >= limit_up: streak += 1
    else: streak = 0

v5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
vr = v[i]/v5 if v5>0 else 99
if i >= 15:
    tr = np.maximum(h[i-14:i]-l[i-14:i],
        np.maximum(abs(h[i-14:i]-c[i-15:i-1]), abs(l[i-14:i]-c[i-15:i-1])))
    atr = np.mean(tr)
else: atr = 0
atr_r = atr/c[i] if c[i]>0 and atr>0 else 1
lc = c[i-streak-1] if streak>=1 else c[i-1]
depth = (c[i]-lc)/lc*100
is_fake = int(c[i] > c[i-1] and c[i] < o[i])
ma20 = pd.Series(c).rolling(20).mean().values
ma20_dev = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
ret20 = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0

feat = np.array([[streak, vr, depth, atr_r, is_fake, ma20_dev, ret20, c[i]]])
feat_df = pd.DataFrame(feat, columns=features).fillna(0)
proba = model.predict_proba(feat_df)[0, 1]
print(f'002432: ML proba={proba:.3f} ({proba*100:.0f}pts), threshold={threshold}')