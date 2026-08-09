# Fast full universe comparison v38 vs v42
import sys, os, pickle, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'
files = sorted([f.replace('.parquet','') for f in os.listdir(CACHE)
         if f.endswith('.parquet') and not f.startswith('_')
         and f[:3] in ('688','002')])

# Load ML model
model_data = pickle.load(open('models/ml_selector.pkl', 'rb'))
ml_model = model_data['model']
ml_features = model_data['features']
ml_threshold = model_data.get('threshold', 0.4)

print(f"Full universe comparison: v38 vs v42 (ML-enhanced)")
print(f"Scanning {len(files)} stocks...")

v38_wins = {}; v42_wins = {}; signal_count = 0

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
            signal_count += 1
            vol_ma5 = np.mean(v[max(0,i-5):i]) if i>=5 else np.mean(v[:i])
            vol_r = v[i]/vol_ma5 if vol_ma5>0 else 99

            if i >= 15:
                tr = np.maximum(h[i-14:i]-l[i-14:i],
                    np.maximum(abs(h[i-14:i]-c[i-15:i-1]),
                              abs(l[i-14:i]-c[i-15:i-1])))
                atr = np.mean(tr)
            else: atr = 0
            atr_r = atr/c[i] if c[i]>0 and atr>0 else 1

            lc = c[i-int(streak[i-1])-1]
            depth = (c[i]-lc)/lc*100
            is_fake = int(c[i] > c[i-1] and c[i] < o[i])

            ma20 = pd.Series(c).rolling(20).mean().values
            ma20_dev = (c[i]-ma20[i])/ma20[i]*100 if not np.isnan(ma20[i]) else 0
            ret_20d = (c[i]-c[max(0,i-20)])/c[max(0,i-20)]*100 if i>=20 else 0

            fwd_ret = (c[i+5]-c[i])/c[i]*100

            # v38 standard: basic filter + trailing stop
            # v42: ML-enhanced scoring
            v42_score = 0
            s = streak[i-1]
            if s == 2: v42_score += 25
            elif s == 3: v42_score += 22
            elif s == 4: v42_score += 12
            elif s >= 5: v42_score += 5
            else: v42_score += 10
            if is_fake: v42_score += 25
            else: v42_score += 5
            if atr_r >= 0.08: v42_score += 15
            elif atr_r >= 0.05: v42_score += 10
            elif atr_r >= 0.03: v42_score += 5
            if vol_r <= 0.3: v42_score += 15
            elif vol_r <= 0.5: v42_score += 12
            elif vol_r <= 0.7: v42_score += 8
            elif vol_r <= 1.0: v42_score += 4
            if depth >= 0: v42_score += 10
            elif depth >= -3: v42_score += 8
            elif depth >= -6: v42_score += 5
            elif depth >= -10: v42_score += 2
            if ma20_dev < 15: v42_score += 5
            elif ma20_dev < 30: v42_score += 2
            else: v42_score -= 3
            v42_score = min(100, max(0, v42_score))

            # v42 trades only if score >= 50
            v42_trades = v42_score >= 50

            # ML final filter
            feat = np.array([[s, vol_r, depth, atr_r, is_fake, ma20_dev, ret_20d, c[i]]])
            feat_df = pd.DataFrame(feat, columns=ml_features).fillna(0)
            ml_proba = ml_model.predict_proba(feat_df)[0, 1]
            ml_passes = ml_proba >= ml_threshold

            v42_final = v42_trades and ml_passes

            if code not in v38_wins:
                v38_wins[code] = {'trades': 0, 'wins': 0, 'losses': 0}
                v42_wins[code] = {'trades': 0, 'wins': 0, 'losses': 0}

            # v38 always trades on signal
            v38_wins[code]['trades'] += 1
            if fwd_ret > 0: v38_wins[code]['wins'] += 1
            else: v38_wins[code]['losses'] += 1

            if v42_final:
                v42_wins[code]['trades'] += 1
                if fwd_ret > 0: v42_wins[code]['wins'] += 1
                else: v42_wins[code]['losses'] += 1

    if (idx+1) % 300 == 0:
        print(f'  {idx+1}/{len(files)} signals={signal_count}')

print(f'\nTotal signals found: {signal_count}')
print(f'Stocks with signals: {len(v38_wins)}')

v38_total = sum(d['trades'] for d in v38_wins.values())
v38_wins_total = sum(d['wins'] for d in v38_wins.values())
v42_total = sum(d['trades'] for d in v42_wins.values())
v42_wins_total = sum(d['wins'] for d in v42_wins.values())

print(f'\n=== v38 (trade every signal) ===')
print(f'Trades: {v38_total}, Win rate: {v38_wins_total/v38_total*100:.1f}%')

print(f'\n=== v42 (ML-enhanced scoring) ===')
print(f'Trades: {v42_total}, Win rate: {v42_wins_total/v42_total*100:.1f}%')
print(f'Filter ratio: {v42_total/v38_total*100:.1f}% (takes only {v42_total/v38_total*100:.0f}% of signals)')

# Stocks that trade better with v42
v42_better = sum(1 for code in v38_wins
    if v42_wins[code]['trades'] > 0
    and v42_wins[code]['wins']/max(v42_wins[code]['trades'],1)
    > v38_wins[code]['wins']/max(v38_wins[code]['trades'],1))
print(f'\nStocks where v42 has higher win rate: {v42_better}/{len(v38_wins)} ({v42_better/len(v38_wins)*100:.0f}%)')
print('Done')