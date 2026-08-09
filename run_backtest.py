# -*- coding: utf-8 -*-
"""龙首阴回测运行+可视化"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtesting import Backtest
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from strategies.custom.dragon_first_yin_v35 import DragonFirstYin
from data.fetch.unified import fetch

def run(code="002456", start="20230101", cash=100000, commission=0.0003):
    data = fetch(code, start=start)
    if data is None or len(data) < 60:
        print(f"数据不足: {code}")
        return None
    
    # 在策略类上设置股票代码
    Strat = type("Run", (DragonFirstYin,), {"stock_code": code})
    bt = Backtest(data, Strat, cash=cash, commission=commission, exclusive_orders=True)
    result = bt.run()
    
    print(f"\n=== {code} 回测结果 ===")
    print(f"  交易次数: {result['# Trades']}")
    print(f"  收益率:   {result['Return [%]']:.2f}%")
    print(f"  年化收益: {result['Return (Ann.) [%]']:.2f}%")
    print(f"  夏普比率: {result['Sharpe Ratio']:.3f}")
    print(f"  最大回撤: {result['Max. Drawdown [%]']:.2f}%")
    print(f"  胜率:     {result['Win Rate [%]']:.1f}%")
    print(f"  盈亏比:   {result['Profit Factor']:.3f}")
    
    return result, data, bt

def plot(result, data, code, save_path=None):
    """画出价格+权益+回撤图"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1.5, 1]})
    
    # 1. 价格曲线 + 买卖点
    ax1 = axes[0]
    ax1.plot(data.index, data['Close'], color='gray', linewidth=0.8, label='Close')
    
    # 提取交易记录
    trades = result._trades
    if trades is not None and len(trades) > 0:
        for _, t in trades.iterrows():
            sz = t.get('Size', 0)
            ep = t.get('EntryPrice', 0)
            et = t.get('EntryTime')
            if sz > 0:
                ax1.scatter(et, ep, marker='^', color='red', s=80, zorder=5)
            else:
                xp = t.get('ExitPrice', 0)
                xt = t.get('ExitTime')
                pnl = (xp - ep) / ep * 100 if ep > 0 else 0
                color = 'green' if pnl > 0 else 'red'
                ax1.scatter(xt, xp, marker='v', color=color, s=80, zorder=5)
    
    ax1.set_title(f'{code} 龙首阴策略回测', fontsize=14)
    ax1.set_ylabel('价格')
    ax1.legend(loc='upper left')
    ax1.grid(alpha=0.3)
    
    # 2. 权益曲线
    ax2 = axes[1]
    equity = result._equity_curve['Equity']
    ax2.plot(equity.index, equity.values, color='blue', linewidth=1)
    ax2.set_ylabel('权益')
    ax2.grid(alpha=0.3)
    
    # 添加关键指标文本
    text = (f"收益率: {result['Return [%]']:.2f}%\n"
            f"夏普: {result['Sharpe Ratio']:.3f}\n"
            f"回撤: {result['Max. Drawdown [%]']:.2f}%\n"
            f"交易: {result['# Trades']}")
    ax2.text(0.02, 0.95, text, transform=ax2.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # 3. 回撤曲线
    ax3 = axes[2]
    dd = result._equity_curve['DrawdownPct'] * 100
    ax3.fill_between(dd.index, 0, dd.values, color='red', alpha=0.3)
    ax3.plot(dd.index, dd.values, color='red', linewidth=0.8)
    ax3.set_ylabel('回撤 %')
    ax3.set_xlabel('日期')
    ax3.grid(alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"图片已保存: {save_path}")
    plt.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='龙首阴回测')
    parser.add_argument('--code', default='002456', help='股票代码')
    parser.add_argument('--start', default='20230101', help='开始日期 YYYYMMDD')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    parser.add_argument('--save', default='results/dragon_yin.png', help='图片保存路径')
    args = parser.parse_args()
    
    result = run(args.code, args.start, args.cash)
    if result is not None:
        plot(result[0], result[1], args.code, args.save)