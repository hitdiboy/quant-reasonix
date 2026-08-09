"""
策略注册入口

顶层入口，统一导出所有策略。添加新策略时只需操作 custom/__init__.py。
"""
from strategies._base import BaseStrategy
from strategies.custom import FLAT_LIST, ALL_CUSTOM, DRAGON_FAMILY, MOMENTUM_FAMILY

STRATEGIES = FLAT_LIST
STRATEGY_BY_NAME = {s.name: s for s in STRATEGIES}
__all__ = STRATEGIES + [
    BaseStrategy, "STRATEGIES", "STRATEGY_BY_NAME",
    "ALL_CUSTOM", "DRAGON_FAMILY", "MOMENTUM_FAMILY",
]