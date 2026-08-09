# -*- coding: utf-8 -*-
"""查AKShare可用的分钟/资金流API"""
import akshare as ak
items = [x for x in dir(ak) if any(k in x.lower() for k in ['min','intra','fund','flow','money','capital','分时','资金'])]
for x in sorted(items):
    print(x)