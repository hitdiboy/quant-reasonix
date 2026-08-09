"""策略筛选流水线

从 DuckDB 结果库中读取所有回测记录，按指定指标阈值过滤、排序。
支持：
  1. 基本筛选（夏普、回撤、收益率、交易次数）
  2. 组合排名（综合打分 = 夏普×权重 − 回撤×权重 + 收益率×权重）
  3. 输出候选清单 → 可自动触发下一轮回测或模拟跟踪
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ScreenCriteria:
    """筛选条件"""
    min_sharpe: float = 0.5
    max_drawdown_pct: float = 25.0
    min_return_pct: float = 0.0
    min_trades: int = 5
    max_trades: int = 99999


@dataclass
class RankWeights:
    """综合排名权重"""
    sharpe: float = 0.5
    return_pct: float = 0.3
    drawdown_penalty: float = 0.2  # 回撤惩罚权重


def screen(criteria: Optional[ScreenCriteria] = None, limit: int = 20) -> "pandas.DataFrame":
    """从数据库筛选达标策略

    Args:
        criteria: 筛选条件，默认夏普>0.5 回撤<25% 收益率>0% 交易>5
        limit: 返回条数上限

    Returns:
        pandas DataFrame
    """
    import pandas as _pd
    from results.vault import query

    c = criteria or ScreenCriteria()

    sql = """
        SELECT strategy_name, symbol, market, params_json,
               ROUND(return_pct, 2) as return_pct,
               ROUND(sharpe_ratio, 3) as sharpe_ratio,
               ROUND(max_drawdown_pct, 2) as drawdown_pct,
               ROUND(win_rate_pct, 1) as win_rate,
               num_trades,
               ROUND(profit_factor, 2) as profit_factor,
               created_at
        FROM backtest_runs
        WHERE sharpe_ratio >= ?
          AND (max_drawdown_pct IS NULL OR max_drawdown_pct <= ?)
          AND (return_pct IS NULL OR return_pct >= ?)
          AND num_trades BETWEEN ? AND ?
        ORDER BY sharpe_ratio DESC
        LIMIT ?
    """
    params = [c.min_sharpe, c.max_drawdown_pct, c.min_return_pct,
              c.min_trades, c.max_trades, limit]

    return query(sql, params)


def rank(criteria: Optional[ScreenCriteria] = None,
         weights: Optional[RankWeights] = None,
         limit: int = 20) -> "pandas.DataFrame":
    """综合打分排名

    score = sharpe×w.sharpe + return_pct×w.return_pct - drawdown_pct×w.drawdown_penalty
    """
    import pandas as _pd
    from results.vault import query

    w = weights or RankWeights()
    c = criteria or ScreenCriteria()

    # 先筛选出达标项
    sql = """
        SELECT strategy_name, symbol, market, params_json,
               sharpe_ratio, return_pct, max_drawdown_pct, win_rate_pct, num_trades
        FROM backtest_runs
        WHERE sharpe_ratio >= ?
          AND max_drawdown_pct <= ?
          AND num_trades >= ?
    """
    params = [c.min_sharpe, c.max_drawdown_pct, c.min_trades]

    df = query(sql, params)
    if df is None or df.empty:
        return df

    # 归一化后打分
    for col in ["sharpe_ratio", "return_pct"]:
        mx, mn = df[col].max(), df[col].min()
        if mx > mn:
            df[f"{col}_norm"] = (df[col] - mn) / (mx - mn)
        else:
            df[f"{col}_norm"] = 0.5

    mn_dd, mx_dd = df["max_drawdown_pct"].min(), df["max_drawdown_pct"].max()
    if mx_dd > mn_dd:
        df["drawdown_inv_norm"] = 1 - (df["max_drawdown_pct"] - mn_dd) / (mx_dd - mn_dd)
    else:
        df["drawdown_inv_norm"] = 0.5

    df["score"] = (
        df["sharpe_ratio_norm"] * w.sharpe +
        df["return_pct_norm"] * w.return_pct +
        df["drawdown_inv_norm"] * w.drawdown_penalty
    )

    return df.sort_values("score", ascending=False).head(limit)


def summary(df, title="策略筛选报告") -> str:
    """打印筛选结果的文本报告"""
    if df is None or df.empty:
        return f"[{title}] 无达标策略"

    lines = [f"===== {title} ====="]
    lines.append(f"达标策略数: {len(df)}")
    lines.append("")

    cols = df.columns.tolist()
    # 判断是 rank() 还是 screen() 的输出
    if "score" in cols:
        lines.append(f"  {'排名':>4s} {'策略名':30s} {'夏普':>8s} {'年化%':>8s} {'回撤%':>8s} {'得分':>8s}")
        lines.append(f"  {'-'*4} {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for i, (_, r) in enumerate(df.iterrows()):
            lines.append(f"  {i+1:>4d} {str(r.get('strategy_name',''))[:28]:30s} "
                         f"{r.get('sharpe_ratio',0):>8.3f} {r.get('return_pct',0):>8.2f} "
                         f"{r.get('max_drawdown_pct',0):>8.2f} {r.get('score',0):>8.4f}")
    else:
        lines.append(f"  {'策略名':30s} {'夏普':>8s} {'年化%':>8s} {'回撤%':>8s} {'交易':>6s} {'胜率%':>7s}")
        lines.append(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*7}")
        for _, r in df.iterrows():
            lines.append(f"  {str(r.get('strategy_name',''))[:28]:30s} "
                         f"{r.get('sharpe_ratio',0):>8.3f} {r.get('return_pct',0):>8.2f} "
                         f"{r.get('drawdown_pct',r.get('max_drawdown_pct',0)):>8.2f} "
                         f"{r.get('num_trades',0):>6d} {r.get('win_rate',r.get('win_rate_pct',0)):>7.1f}")

    return "\n".join(lines)