"""
策略工厂

提供策略查找、实例化和参数网格展开功能。
"""
from strategies import STRATEGIES, STRATEGY_BY_NAME, BaseStrategy
from config.strategy_grids import GRIDS


def lookup(name: str):
    """按注册名查找策略类"""
    cls = STRATEGY_BY_NAME.get(name)
    if cls is None:
        raise KeyError(f"未知策略: {name}，可用策略: {list(STRATEGY_BY_NAME.keys())}")
    return cls


def create(name: str, **kwargs):
    """创建策略实例，可覆盖默认参数"""
    cls = lookup(name)
    return cls(**kwargs)


def by_names(names: list[str]):
    """批量查找多个策略类"""
    return [lookup(n) for n in names]


def expand(grid_key: str = None):
    """
    展开参数网格，返回 (策略类, 参数字典) 列表。

    如果 grid_key 为 None，返回所有网格；否则只返回指定网格。
    """
    result = []
    for cls in STRATEGIES:
        name = cls.name
        if name not in GRIDS:
            continue
        for params in GRIDS[name]:
            result.append((cls, params))
    return result


def info(name: str = None):
    """查看策略元信息"""
    if name:
        return lookup(name).info()
    return {s.name: s.info() for s in STRATEGIES}