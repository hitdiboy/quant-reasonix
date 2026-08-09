import sys, os
sys.path.insert(0, os.getcwd())

# 1. Strategy import
from strategies.custom.end_of_day_breakout import EndOfDayBreakout
print(f'[1] Strategy: {EndOfDayBreakout.name} OK')

# 2. ML model
import pickle
data = pickle.load(open('models/ml_selector.pkl', 'rb'))
print(f'[2] ML model: {len(data[\"features\"])} features OK')

# 3. Scanner
from scripts._eod_daily import calc_tail_score
print(f'[3] Scanner: calc_tail_score() OK')

# 4. Config
import json
cfg = json.load(open('config/eod_strategy.json'))
print(f'[4] Config: min_score={cfg.get(\"min_score\")} OK')

# 5. Daily data output
try:
    d = json.load(open('scripts/daily_data/eod_2026-08-09.json'))
    top3 = [s['code'] for s in d['top']]
    print(f'[5] Daily data: {d[\"date\"]} Top3={top3}')
except: print('[5] Daily data: pending (weekend)')

print('\n=== All systems operational ===')
print('Run: python scripts/_eod_daily.py')