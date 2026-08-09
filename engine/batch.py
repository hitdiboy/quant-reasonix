"""批量回测驱动器"""
import time as _time
from typing import Any, Callable, Dict, List


def run_batch(variants, data_getter: Callable, cash=100000, commission=0.0003, slippage=0.0, sim_config=None, tag="") -> Dict:
    """运行一批策略变体"""
    from engine.backtest import run as _run_single
    start_ts = _time.time()
    outcomes = []
    for i, variant in enumerate(variants):
        outcome = {"variant_name": variant.variant_name, "params": dict(variant.params), "index": i}
        try:
            symbol = getattr(variant, "symbol", "")
            start_date = getattr(variant, "start", "20200101")
            end_date = getattr(variant, "end", "")
            data = data_getter(symbol=symbol, start=start_date, end=end_date)
            if data is None or len(data) < 50:
                outcome["status"] = "skipped"
                outcome["error"] = f"数据不足({len(data) if data is not None else 0}行)"
                outcomes.append(outcome)
                continue
            cls = variant.strategy_class
            for k, v in variant.params.items():
                setattr(cls, k, v)
            result, metrics, risk = _run_single(cls, data, cash=cash, commission=commission, slippage=slippage, sim_config=sim_config, auto_save=False)
            outcome["status"] = "success"
            outcome["return_pct"] = metrics.get("年化收益率%", 0)
            outcome["sharpe_ratio"] = metrics.get("夏普比率", 0)
            outcome["max_drawdown_pct"] = metrics.get("最大回撤%", 0)
            outcome["num_trades"] = metrics.get("交易次数", 0)
            outcome["metrics"] = metrics
            outcome["result"] = result
            outcome["risk"] = risk
        except Exception as e:
            outcome["status"] = "failed"
            outcome["error"] = str(e)
        outcomes.append(outcome)
    elapsed = _time.time() - start_ts
    return {
        "total": len(variants),
        "success": sum(1 for o in outcomes if o.get("status") == "success"),
        "failed": sum(1 for o in outcomes if o.get("status") == "failed"),
        "results": outcomes,
        "elapsed_sec": round(elapsed, 2),
        "tag": tag,
    }


def print_report(report: Dict):
    """打印批次回测报告"""
    print(f"===== 批次报告 [{report.get('tag', '')}] =====")
    print(f"  总数: {report['total']}  |  成功: {report['success']}  |  失败: {report['failed']}")
    print(f"  耗时: {report['elapsed_sec']}s")
    print()
    ok = [o for o in report["results"] if o.get("status") == "success"]
    ok.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
    print(f"--- 成功 Top10 (夏普降序) ---")
    print(f"  {'变体':40s} {'年化%':>8s} {'夏普':>8s} {'回撤%':>8s} {'交易':>6s}")
    print(f"  {'-'*40} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
    for o in ok[:10]:
        n = o["variant_name"][:38]
        r = o.get("return_pct", 0)
        s = o.get("sharpe_ratio", 0)
        d = o.get("max_drawdown_pct", 0)
        t = o.get("num_trades", 0)
        print(f"  {n:40s} {r:>8.2f} {s:>8.3f} {d:>8.2f} {t:>6d}")
    if report["failed"] > 0:
        print(f"\n--- 失败项 ---")
        for o in report["results"]:
            if o.get("status") == "failed":
                print(f"  [FAIL] {o['variant_name']}: {o.get('error', '未知')}")