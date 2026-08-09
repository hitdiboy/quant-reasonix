# -*- coding: utf-8 -*-
"""自定义策略注册入口

命名规范: 策略类型_版本号.py → 类名含版本号
添加新策略只需:
  1. 在 custom/ 下创建文件
  2. 在此文件中 import + 加入对应家族

家族分类:
  dragon_*         — 龙首阴策略家族 (v35→v42)
  momentum_*       — 动量/突破类策略
  end_of_day_*     — 尾盘隔夜超短战法
  trend_*          — 趋势跟踪类策略 (待扩展)
  ml_*             — ML/因子选股类策略 (待扩展)
"""
from .dragon_first_yin_v35 import DragonFirstYin as DragonFirstYinV35
from .dragon_first_yin_v36 import DragonFirstYinV36
from .dragon_first_yin_v37 import DragonFirstYinV37
from .dragon_first_yin_v38 import DragonFirstYinV38
from .dragon_first_yin_v39 import DragonFirstYinV39
from .dragon_first_yin_v40 import DragonFirstYinV40
from .dragon_first_yin_v41 import DragonFirstYinV41
from .dragon_first_yin_v42 import DragonFirstYinV42
from .momentum_breakout import MomentumBreakout
from .end_of_day_breakout import EndOfDayBreakout

# 按家族分组索引
DRAGON_FAMILY = [
    DragonFirstYinV35, DragonFirstYinV36, DragonFirstYinV37,
    DragonFirstYinV38, DragonFirstYinV39, DragonFirstYinV40,
    DragonFirstYinV41, DragonFirstYinV42,
]
MOMENTUM_FAMILY = [MomentumBreakout]
END_OF_DAY_FAMILY = [EndOfDayBreakout]

ALL_CUSTOM = {
    "dragon": DRAGON_FAMILY,
    "momentum": MOMENTUM_FAMILY,
    "end_of_day": END_OF_DAY_FAMILY,
}

FLAT_LIST = []
for family in ALL_CUSTOM.values():
    FLAT_LIST.extend(family)

__all_custom__ = FLAT_LIST
__all__ = FLAT_LIST + [
    "DRAGON_FAMILY", "MOMENTUM_FAMILY", "END_OF_DAY_FAMILY", "ALL_CUSTOM"
]