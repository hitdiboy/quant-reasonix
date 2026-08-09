# -*- coding: utf-8 -*-
# 腾讯实时行情接口 (qt.gtimg.cn)
import os as _os, requests as _rq, re as _re

def _clean_proxy():
    for k in list(_os.environ.keys()):
        if k.lower().endswith('_proxy') or k.lower() == 'no_proxy':
            _os.environ.pop(k, None)

def _code_to_tencent(code):
    if code.startswith('6'):
        return 'sh' + code
    return 'sz' + code

def get_realtime_quotes(codes, timeout=10):
    if not codes:
        return {}
    _clean_proxy()
    tencodes = [_code_to_tencent(c) for c in codes]
    url = 'http://qt.gtimg.cn/q=' + ','.join(tencodes)
    try:
        r = _rq.get(url, timeout=timeout)
        r.encoding = 'gbk'
        text = r.text
    except Exception as e:
        print('  Tencent quote failed: ' + str(e))
        return {}
    results = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or not line.startswith('v_'):
            continue
        m = _re.match(r'v_\w+="(.+)"', line)
        if not m:
            continue
        parts = m.group(1).split('~')
        if len(parts) < 35:
            continue
        code = parts[2]
        try:
            results[code] = {
                'name': parts[1],
                'price': float(parts[3]) if parts[3] else 0,
                'open': float(parts[5]) if parts[5] else 0,
                'high': float(parts[33]) if parts[33] else 0,
                'low': float(parts[34]) if parts[34] else 0,
                'prev_close': float(parts[4]) if parts[4] else 0,
                'change': float(parts[31]) if parts[31] else 0,
                'change_pct': float(parts[32]) if parts[32] else 0,
                'volume': int(parts[6]) if parts[6] else 0,
                'time': parts[30] if len(parts) > 30 else '',
            }
        except (ValueError, IndexError):
            continue
    return results

def get_realtime_price(code, timeout=10):
    q = get_realtime_quotes([code], timeout=timeout)
    return q.get(code, {})

if __name__ == '__main__':
    q = get_realtime_quotes(['300592', '002212', '688001'])
    for c, d in q.items():
        nm = d.get('name', '?')
        pr = d.get('price', 0)
        cp = d.get('change_pct', 0)
        vl = d.get('volume', 0)
        tm = d.get('time', '')
        print(f'{c} {nm}: {pr} ({cp:+.2f}%) vol:{vl} time:{tm}')