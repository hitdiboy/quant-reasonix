import duckdb as _db
import json as _json
import os as _os

_DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'vault.db')

def _connect_db():
    return _db.connect(_DB_PATH)

def init():
    conn = _connect_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id INTEGER PRIMARY KEY,
            strategy_name TEXT NOT NULL,
            strategy_version TEXT DEFAULT '',
            symbol TEXT DEFAULT '',
            market TEXT DEFAULT '',
            params_json TEXT DEFAULT '{}',
            return_pct REAL,
            annual_return_pct REAL,
            annual_volatility_pct REAL,
            sharpe_ratio REAL,
            max_drawdown_pct REAL,
            calmar_ratio REAL,
            win_rate_pct REAL,
            profit_factor REAL,
            num_trades INTEGER,
            sqn REAL,
            equity_final REAL,
            start_date TEXT,
            end_date TEXT,
            cash REAL,
            commission REAL,
            slippage REAL DEFAULT 0.0,
            risk_warnings_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.close()

def save_run(strategy_name, metrics, result, risk, params=None, symbol='', market='', cash=100000, commission=0.0003, slippage=0.0, sim_config=None):
    conn = _connect_db()
    next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM backtest_runs").fetchone()[0]
    try:
        equity = float(result.get('Equity Final [$]', 0))
    except (KeyError, TypeError, AttributeError):
        equity = 0.0
    try:
        start = str(result.index[0].date()) if hasattr(result, 'index') else ''
        end = str(result.index[-1].date()) if hasattr(result, 'index') else ''
    except (IndexError, TypeError, AttributeError):
        start, end = '', ''
    conn.execute('''
        INSERT INTO backtest_runs (
            id, strategy_name, strategy_version, symbol, market, params_json,
            return_pct, annual_return_pct, annual_volatility_pct,
            sharpe_ratio, max_drawdown_pct, calmar_ratio,
            win_rate_pct, profit_factor, num_trades, sqn, equity_final,
            start_date, end_date, cash, commission, slippage, risk_warnings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        next_id, strategy_name, '', symbol, market,
        _json.dumps(params or {}, ensure_ascii=False),
        metrics.get('年化收益率%', 0), metrics.get('年化收益%', 0),
        metrics.get('年化波动%', 0), metrics.get('夏普比率', 0),
        metrics.get('最大回撤%', 0), metrics.get('卡玛比率', 0),
        metrics.get('胜率%', 0), metrics.get('盈亏比', 0),
        metrics.get('交易次数', 0), metrics.get('SQN', 0),
        equity, start, end, cash, commission, slippage,
        _json.dumps(risk, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()
    return next_id

def query(sql, params=None):
    conn = _connect_db()
    result = conn.execute(sql, params or []).fetchdf()
    conn.close()
    return result

init()