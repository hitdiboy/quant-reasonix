# 交接文档 — 量化交易项目 (quant-reasonix)
# 最后更新: 2026-08-09

## 当前活跃状态

- 阶段: 龙首阴v35 移植完成（从 quant-codex）
- 策略版本: v35（板块轮动+MACD/KDJ+动态加仓）
- 板块限定: 创业板300 + 中小板002 + 科创板688
- 数据缓存: 指向 quant-codex 缓存目录

## 移植修复

- 新增 `_use_board_params = True` 类属性，设为 False 跳过 `_apply_board_params()` 覆盖参数
- 这是原 v35 策略 `init()` 覆盖用户参数字段导致 0 笔交易的根因

## 快速启动

```bash
cd C:\Users\Administrator\AppData\Roaming\reasonix\global-workspace\quant-reasonix

# 验证导入
python -c "from strategies.custom.strategy_001_dragon_first_yin import DragonFirstYin; print('OK:', DragonFirstYin.description)"

# 单只回测
python run_backtest.py --code=002456 --start=20230101 --save=results/dragon_yin.png

# 全量回测
python scripts/_run_all_stocks.py
```

## 回测验证

| 项目 | 结果 |
|------|------|
| 导入验证 | 19/19 全过 |
| 端到端回测 (002456 2023-2026) | 2笔交易, 收益0.92%, 夏普0.186 |
| 端到端回测 (002456 2024) | 4笔交易, 收益4.28%, 夏普0.46 |

## 文件清单 (37个文件)

```
.gitignore  AGENTS.md  README.md
_sop/lessons.md
config/strategy_grids.py  config/symbols.py
data/__init__.py  data/fetch/__init__.py
data/fetch/akshare_data.py  data/fetch/tencent_realtime.py  data/fetch/unified.py
engine/__init__.py  engine/backtest.py  engine/batch.py
engine/costs.py  engine/metrics.py  engine/risk.py
engine/screener.py  engine/sim_rules.py
paper_trading/__init__.py  paper_trading/dragon_monitor.py
paper_trading/monitor.py  paper_trading/reporter.py
paper_trading/simulator.py  paper_trading/tracker.py
results/__init__.py  results/query.py  results/vault.py
run_backtest.py  scripts/_run_all_stocks.py
strategies/__init__.py  strategies/_base.py
strategies/custom/__init__.py  strategies/custom/strategy_001_dragon_first_yin.py
strategies/factory.py
tracking/handover.md  tracking/run_dragon_realtime.ps1
```