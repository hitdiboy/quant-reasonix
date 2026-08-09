"""
参数网格配置

GRIDS 字典: 策略名称 → 参数组合列表
每个参数组合是一个 dict，覆盖策略的默认参数。

用于策略工厂的 expand() 方法生成全参数空间回测任务。
"""

GRIDS = {
    # ===== 龙首阴 v35 =====
    "龙首阴": [
        {
            "min_limit_ups": 2,
            "max_vol_ratio": 3.0,
            "atr_ratio_limit": 0.18,
            "yin_depth_pct": -12.0,
            "base_entry_pct": 0.10,
            "max_entry_pct": 0.20,
            "max_hold_days": 20,
            "use_macd_filter": True,
            "use_kdj_filter": True,
            "use_index_filter": True,
            "use_signal_scoring": True,
        },
        # 激进版本 (放宽限制)
        {
            "min_limit_ups": 1,
            "max_vol_ratio": 4.0,
            "atr_ratio_limit": 0.22,
            "yin_depth_pct": -15.0,
            "base_entry_pct": 0.12,
            "max_entry_pct": 0.25,
            "max_hold_days": 25,
            "use_macd_filter": False,
            "use_kdj_filter": False,
            "use_index_filter": True,
            "use_signal_scoring": True,
        },
        # 保守版本 (严格限制)
        {
            "min_limit_ups": 3,
            "max_vol_ratio": 2.0,
            "atr_ratio_limit": 0.15,
            "yin_depth_pct": -8.0,
            "base_entry_pct": 0.08,
            "max_entry_pct": 0.15,
            "max_hold_days": 15,
            "use_macd_filter": True,
            "use_kdj_filter": True,
            "use_index_filter": True,
            "use_signal_scoring": True,
        },
    ],
}