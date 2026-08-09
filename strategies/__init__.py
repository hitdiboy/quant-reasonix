"""
策略注册入口

注册本项目所有可用策略。
"""
from strategies._base import BaseStrategy
from strategies.custom.strategy_001_dragon_first_yin import DragonFirstYin
from strategies.custom.strategy_002_dragon_first_yin_v36 import DragonFirstYinV36
from strategies.custom.strategy_003_dragon_first_yin_v37 import DragonFirstYinV37
from strategies.custom.strategy_004_dragon_first_yin_v38 import DragonFirstYinV38
from strategies.custom.strategy_005_dragon_first_yin_v39 import DragonFirstYinV39
from strategies.custom.strategy_006_dragon_first_yin_v40 import DragonFirstYinV40
from strategies.custom.strategy_007_dragon_first_yin_v41 import DragonFirstYinV41
from strategies.custom.strategy_008_dragon_first_yin_v42 import DragonFirstYinV42
from strategies.momentum_breakout import MomentumBreakout

STRATEGIES = [
    DragonFirstYin, DragonFirstYinV36, DragonFirstYinV37,
    DragonFirstYinV38, DragonFirstYinV39, DragonFirstYinV40,
    DragonFirstYinV41, DragonFirstYinV42, MomentumBreakout,
]
STRATEGY_BY_NAME = {s.name: s for s in STRATEGIES}
__all__ = STRATEGIES + [BaseStrategy, "STRATEGIES", "STRATEGY_BY_NAME"]