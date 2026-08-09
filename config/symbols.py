# Stock universe configuration
# Market: A=China A-share, HK=Hong Kong, US=United States

# === A股个股 (核心池) ===
A_STOCKS = [
    {"code":"600519","name":"贵州茅台","exchange":"SH","type":"stock","market":"A"},
    {"code":"000858","name":"五粮液","exchange":"SZ","type":"stock","market":"A"},
    {"code":"600036","name":"招商银行","exchange":"SH","type":"stock","market":"A"},
    {"code":"601318","name":"中国平安","exchange":"SH","type":"stock","market":"A"},
    {"code":"000333","name":"美的集团","exchange":"SZ","type":"stock","market":"A"},
    {"code":"600900","name":"长江电力","exchange":"SH","type":"stock","market":"A"},
    {"code":"002415","name":"海康威视","exchange":"SZ","type":"stock","market":"A"},
    {"code":"600276","name":"恒瑞医药","exchange":"SH","type":"stock","market":"A"},
    {"code":"000002","name":"万科A", "exchange":"SZ","type":"stock","market":"A"},
    {"code":"601166","name":"兴业银行","exchange":"SH","type":"stock","market":"A"},
]

# === A股ETF ===
A_ETFS = [
    {"code":"510300","name":"沪深300ETF","exchange":"SH","type":"etf","market":"A"},
    {"code":"510050","name":"上证50ETF","exchange":"SH","type":"etf","market":"A"},
    {"code":"159915","name":"创业板ETF","exchange":"SZ","type":"etf","market":"A"},
    {"code":"159949","name":"创业板50ETF","exchange":"SZ","type":"etf","market":"A"},
    {"code":"588000","name":"科创板50ETF","exchange":"SH","type":"etf","market":"A"},
]

# === 美股 (yfinance 实时数据) ===
US_STOCKS = [
    {"code":"SPY","name":"S&P 500 ETF","exchange":"NYSE","type":"etf","market":"US"},
    {"code":"QQQ","name":"NASDAQ 100 ETF","exchange":"NASDAQ","type":"etf","market":"US"},
    {"code":"AAPL","name":"Apple","exchange":"NASDAQ","type":"stock","market":"US"},
    {"code":"MSFT","name":"Microsoft","exchange":"NASDAQ","type":"stock","market":"US"},
    {"code":"GOOGL","name":"Google","exchange":"NASDAQ","type":"stock","market":"US"},
    {"code":"AMZN","name":"Amazon","exchange":"NASDAQ","type":"stock","market":"US"},
    {"code":"TSLA","name":"Tesla","exchange":"NASDAQ","type":"stock","market":"US"},
    {"code":"NVDA","name":"NVIDIA","exchange":"NASDAQ","type":"stock","market":"US"},
]

# === 港股 ===
HK_STOCKS = [
    {"code":"0700","name":"腾讯控股","exchange":"HKEX","type":"stock","market":"HK"},
    {"code":"9988","name":"阿里巴巴","exchange":"HKEX","type":"stock","market":"HK"},
]

# === 指数 (用于基准对比) ===
INDICES = {
    "HSI": "恒生指数",
    "SPY": "S&P 500",
}

# === 全量标的清单 (快捷引用) ===
ALL_SYMBOLS = A_STOCKS + A_ETFS + US_STOCKS + HK_STOCKS

def by_market(market="A"):
    """Filter symbols by market."""
    return [s for s in ALL_SYMBOLS if s["market"] == market]

def by_type(type_="stock"):
    """Filter symbols by type."""
    return [s for s in ALL_SYMBOLS if s["type"] == type_]