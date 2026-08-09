"""
策略注册入口

注册本项目所有可用策略。策略类必须继承 BaseStrategy。
"""
from strategies._base import BaseStrategy
from strategies.custom.strategy_001_dragon_first_yin import DragonFirstYin
from strategies.custom.strategy_002_dragon_first_yin_v36 import DragonFirstYinV36
from strategies.custom.strategy_003_dragon_first_yin_v37 import DragonFirstYinV37
from strategies.custom.strategy_004_dragon_first_yin_v38 import DragonFirstYinV38
from strategies.custom.strategy_005_dragon_first_yin_v39 import DragonFirstYinV39

# ======== 策略注册表 ========
__all_custom__ = [DragonFirstYin, DragonFirstYinV36, DragonFirstYinV37, DragonFirstYinV38, DragonFirstYinV39]
STRATEGIES = [
    DragonFirstYin, DragonFirstYinV36, DragonFirstYinV37,
    DragonFirstYinV38, DragonFirstYinV39,
]

# 注册名索引
STRATEGY_BY_NAME = {s.name: s for s in STRATEGIES}
__all__ = STRATEGIES + [BaseStrategy, "STRATEGIES", "STRATEGY_BY_NAME"]