import os, sys
for k in list(os.environ.keys()):
    kl = k.lower()
    if kl.endswith('_proxy') or kl == 'no_proxy':
        os.environ.pop(k, None)

import akshare as ak

df = ak.stock_zh_a_hist_min_em(symbol="002456", period="5", start_date="20260807", end_date="20260809")
print("分钟数据列:", list(df.columns))
print("形状:", df.shape)
print(df.tail(5))