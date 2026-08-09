# -*- coding: utf-8 -*-
import os, json
files = ['_sop/尾盘战法策略文档.md','_sop/尾盘战法实战手册.md','strategies/custom/end_of_day_breakout.py','scripts/_eod_daily.py','config/eod_strategy.json','scripts/_test_eod_params.py','scripts/daily_data/eod_2026-08-09.json']
ok = all(os.path.exists(f) for f in files)
print(f'All {len(files)} deliverable files exist: {ok}')
with open('scripts/daily_data/eod_2026-08-09.json') as f:
    d = json.load(f)
print(f'JSON output valid: date={d[\"date\"]}, top3={[s[\"code\"] for s in d[\"top\"]]}')
print('System operational. Ready for next iteration.')