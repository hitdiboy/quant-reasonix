# 量化交易系统 (quant-reasonix)

龙首阴策略移植版。从 quant-codex 移植龙首阴 v35 策略及完整回测引擎。

## 目录结构

```
strategies/         策略核心（基类 + DragonFirstYin v35）
data/fetch/         数据获取层（unified + akshare + 腾讯实时行情）
engine/             回测引擎（统一入口 + 绩效指标 + 风控 + 成本 + 批量回测）
results/            DuckDB 结果库（自动建表 + 查询接口）
config/             标的配置 + 参数网格
paper_trading/      模拟交易层（模拟器 + 报告 + 龙首阴监控）
tracking/           交接文档 + 定时任务脚本
scripts/            全量回测脚本
_sop/               项目经验
```

## 快速启动

```bash
# 验证策略导入
python -c "from strategies.custom.dragon_first_yin_v35 import DragonFirstYin; print('OK:', DragonFirstYin.description)"

# 单只股票回测示例
python -c "
from backtesting import Backtest
from strategies.custom.dragon_first_yin_v35 import DragonFirstYin
from data.fetch.unified import fetch

data = fetch('002456', start='20230101')
bt = Backtest(data, DragonFirstYin, cash=100000, commission=0.0003)
result = bt.run()
print(result)
"

# 龙首阴监控扫描
python paper_trading/dragon_monitor.py --scan
```

## 数据说明

缓存数据存储在 quant-codex 项目中（C:\Users\Administrator\Codex-Workspace\quant-codex\data\cache\），通过 unified.py 自动读取。