# -*- coding: utf-8 -*-
import os
path = r'C:\Users\Administrator\AppData\Roaming\reasonix\global-workspace\quant-reasonix\scripts\_eod_daily.py'
with open(path, encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'if c[i] < 100: s4 += 5\n    s4 = min(s4, 25)\n    rule_score = s1 + s2 + s3 + s4',
    'if c[i] < 30: s4 += 5\n    elif c[i] < 60: s4 += 3\n    s4 = min(s4, 25)\n    rule_score = s1 + s2 + s3 + s4'
)
content = content.replace(
    '\n    # --- ML score ---',
    '\n    if c[i] > 100: return None\n    # --- ML score ---'
)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')