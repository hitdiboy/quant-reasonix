# -*- coding: utf-8 -*-
"""交易级深度分析 — 逐笔拆解 v36 每笔交易的盈亏归因"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, numpy as np
from backtesting import Backtest
from strategies.custom.strategy_002_dragon_first_yin_v36 import DragonFirstYinV36

CACHE = r'C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache'

# 选择交易最多的几只做深度分析
codes = ['002432', '002164', '002211', '002178', '002400', '002456']

for code in codes:
    try:
        df = pd.read_parquet(os.path.join(CACHE, f'{code}.parquet'))
        col_map = {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'}
        rename = {c: col_map.get(c.lower().strip(), c) for c in df.columns if c.lower().strip() in col_map}
        df = df.rename(columns=rename)
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.set_index('trade_date')
        df = df[['Open','High','Low','Close','Volume']].dropna().sort_index()
        df.index.name = 'Date'
        if len(df) < 200: continue
    except:
        continue

    Strat = type('T', (DragonFirstYinV36,), {'stock_code': code})
    bt = Backtest(df, Strat, cash=100000, commission=0.0003)
    result = bt.run()

    trades = result._trades
    if trades is None or len(trades) == 0:
        print(f'\n=== {code}: 0 trades ===')
        continue

    print(f'\n=== {code}: {len(trades)} trades ===')
    # 逐笔分析
    winners = 0
    losers = 0
    total_pnl = 0
    hold_times = []
    exit_reasons = []

    for _, t in trades.iterrows():
        entry_time = t['EntryTime']
        exit_time = t['ExitTime']
        entry_price = t['EntryPrice']
        exit_price = t['ExitPrice']
        size = t['Size']
        pnl = t['PnL']
        return_pct = (exit_price - entry_price) / entry_price * 100
        bars_held = (exit_time - entry_time).days

        is_win = pnl > 0
        if is_win:
            winners += 1
        else:
            losers += 1
        total_pnl += pnl
        hold_times.append(bars_held)

        # 推断出场原因
        if return_pct >= 20:
            reason = 'TAKE_PROFIT'
        elif bars_held >= 15:
            reason = 'TIME_STOP'
        else:
            reason = 'TRAILING_STOP'
        exit_reasons.append(reason)

        print(f'  {str(entry_time.date()):>12} -> {str(exit_time.date()):>12} '
              f'hold={bars_held:>2}d entry={entry_price:>7.2f} exit={exit_price:>7.2f} '
              f'pnl={pnl:>+8.2f} ({return_pct:>+6.2f}%) {reason}')

    # 汇总
    win_rate = winners / len(trades) * 100
    avg_hold = np.mean(hold_times)
    print(f'  --- Summary: wins={winners} losses={losers} WR={win_rate:.1f}% '
          f'avg_hold={avg_hold:.1f}d total_pnl={total_pnl:+.2f}')
    # 出场原因分布
    from collections import Counter
    reason_dist = Counter(exit_reasons)
    for r, c in reason_dist.most_common():
        print(f'    {r}: {c}次 ({c/len(trades)*100:.0f}%)')