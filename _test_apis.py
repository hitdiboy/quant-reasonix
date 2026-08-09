"""Test all available APIs"""
import os
for k in list(os.environ.keys()):
    kl = k.lower()
    if kl.endswith('_proxy') or kl == 'no_proxy':
        os.environ.pop(k, None)

import akshare as ak
import time

tests = [
    ("ak.stock_zh_a_hist", "stock_zh_a_hist", {"symbol": "002456", "period": "daily", "start_date": "20260101", "adjust": "qfq"}),
]

for name, fn_name, kwargs in tests:
    try:
        t0 = time.time()
        fn = getattr(ak, fn_name)
        df = fn(**kwargs)
        t = time.time() - t0
        print(f"[{t:.1f}s] {name}: OK ({len(df)} rows)")
    except Exception as e:
        print(f"[FAIL] {name}: {str(e)[:80]}")