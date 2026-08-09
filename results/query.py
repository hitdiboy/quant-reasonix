from results.vault import query as _query

def compare(min_sharpe=0.0, min_trades=5):
    return _query("""
        SELECT strategy_name, symbol, params_json,
               ROUND(sharpe_ratio, 3) as sharpe,
               ROUND(return_pct, 2) as ret_pct,
               ROUND(max_drawdown_pct, 2) as dd_pct,
               ROUND(win_rate_pct, 1) as win_rate,
               num_trades, created_at
        FROM backtest_runs
        WHERE sharpe_ratio >= ? AND num_trades >= ?
        ORDER BY sharpe_ratio DESC
    """, [min_sharpe, min_trades])

def screen(min_sharpe=1.0, max_dd=20.0, min_trades=5):
    return _query("""
        SELECT strategy_name, symbol, params_json,
               ROUND(sharpe_ratio, 3) as sharpe,
               ROUND(max_drawdown_pct, 2) as dd,
               ROUND(return_pct, 2) as ret,
               ROUND(win_rate_pct, 1) as win_rate,
               num_trades
        FROM backtest_runs
        WHERE sharpe_ratio >= ? AND max_drawdown_pct <= ? AND num_trades >= ?
        ORDER BY sharpe_ratio DESC
    """, [min_sharpe, max_dd, min_trades])

def best(metric="sharpe_ratio", limit=10):
    sql = f"""
        SELECT strategy_name, symbol, ROUND({metric}, 3) as val,
               ROUND(return_pct, 2) as ret, ROUND(max_drawdown_pct, 2) as dd,
               num_trades
        FROM backtest_runs
        ORDER BY {metric} DESC LIMIT {limit}
    """
    return _query(sql)