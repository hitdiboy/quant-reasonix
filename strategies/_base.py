# 策略基类
#
# 所有策略继承此类，覆盖 init() 和 next()。
# 兼容 backtesting.py 运行引擎。

from backtesting import Strategy as _Strategy


class BaseStrategy(_Strategy):
    """量化项目统一策略基类"""

    # ---- 子类必须覆盖 ----
    name = ""
    description = ""
    params = {}  # 参数名 → (默认值, 说明)

    def init(self):
        """初始化指标。在回测开始前调用一次。"""
        raise NotImplementedError

    def next(self):
        """每根K线执行一次。回测逐根调用。"""
        raise NotImplementedError

    # ---- 元信息 ----
    @classmethod
    def info(cls) -> dict:
        return {
            "name": cls.name,
            "description": cls.description,
            "params": cls.params,
        }