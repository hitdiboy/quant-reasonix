# A股数据获取（AKShare）
#
# 统一封装，返回标准格式 DataFrame：
#   index: DatetimeIndex (北京时间)
#   columns: Open, High, Low, Close, Volume

import io as _io
import pandas as _pd
import akshare as _ak
import os as _os

def _call_akshare(func, *args, **kwargs):
    """Call AKShare with proxy env vars cleared, retry once on failure."""
    saved = {}
    for k in list(_os.environ.keys()):
        kl = k.lower()
        if kl.endswith("_proxy") or kl == "no_proxy":
            saved[k] = _os.environ.pop(k, None)
    try:
        return func(*args, **kwargs)
    except Exception as e:
        import time as _time
        _time.sleep(1.5)
        try:
            return func(*args, **kwargs)
        except Exception as e2:
            raise RuntimeError(f"AKShare调用失败(已重试1次): {e2}") from e
    finally:
        for k, v in saved.items():
            if v is not None:
                _os.environ[k] = v

def fetch_stock_daily(symbol: str, start: str = "20200101", end: str = None) -> _pd.DataFrame:
    """获取A股个股日线数据"""
    try:
        df = _call_akshare(_ak.stock_zh_a_hist, 
            symbol=symbol, period="daily",
            start_date=start, end_date=end or "", adjust="qfq",
        )
    except Exception as e:
        raise RuntimeError(f"A股日线获取失败 [{symbol}]: {e}")
    if df.empty:
        raise ValueError(f"空数据 [{symbol}]")
    df = df.rename(columns={
        "日期": "Date", "开盘": "Open", "最高": "High",
        "最低": "Low", "收盘": "Close", "成交量": "Volume",
    })
    df["Date"] = _pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df.index.name = "Date"
    return df.sort_index()

def fetch_index_daily(symbol: str, start: str = "20200101", end: str = None) -> _pd.DataFrame:
    """获取A股指数日线数据"""
    try:
        df = _call_akshare(_ak.stock_zh_index_daily, symbol="sh" + symbol)
    except Exception as e:
        raise RuntimeError(f"指数日线获取失败 [{symbol}]: {e}")
    if df.empty:
        raise ValueError(f"空数据 [{symbol}]")
    df = df.rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    })
    df["Date"] = _pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df.index.name = "Date"
    return df.sort_index()