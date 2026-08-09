# AGENTS.md — 项目特有信息

## 项目定位
龙首阴策略量化系统，从 quant-codex 移植。

## 快速指令
- 回测单只: `python -c "from engine.backtest import run; from strategies.custom.strategy_001_dragon_first_yin import DragonFirstYin; from data.fetch.unified import fetch; data=fetch('002456',start='20230101'); r,m,risk=run(DragonFirstYin,data); print(m)"`
- 全量回测: `python scripts/_run_all_stocks.py`
- 龙首阴监控: `python paper_trading/dragon_monitor.py`