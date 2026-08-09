# 统一回测入口
#
# 用法:
#   from engine.backtest import run
#   result, metrics, risk = run(MaCross, data, cash=100000)
#
# sim_config 支持字段:
#   min_commission (5.0), stamp_duty_rate (0.0005), transfer_fee_rate (0.00001),
#   slippage_rate (0.001), limit_up_down (True), t_plus_1 (True),
#   min_trade_unit (100), max_single_position (0.2), stop_loss (0.15),
#   partial_fill (True), cash_t_plus_1 (False)

from backtesting import Backtest as _Backtest
from engine.metrics import extract_metrics
from engine.risk import check_survival_bias, check_trading_costs


def run(
    strategy_class,
    data,
    cash: float = 100000,
    commission: float = 0.0003,
    slippage: float = 0.0,
    sim_config: dict = None,
    exclusive_orders: bool = True,
    auto_save: bool = True,
    **kwargs,
):
    """统一回测入口"""
    # ---- 风控前置检查 ----
    risk_warnings = {
        "survival_bias": check_survival_bias(data, strategy_class.name),
        "trading_costs": check_trading_costs(commission, slippage),
    }
    # ---- 实盘模拟配置 ----
    if sim_config is None:
        sim_config = {}
    sc = {
        "commission_rate": commission,
        "min_commission": sim_config.get("min_commission", 5.0),
        "stamp_duty_rate": sim_config.get("stamp_duty_rate", 0.0005),
        "transfer_fee_rate": sim_config.get("transfer_fee_rate", 0.00001),
        "slippage_rate": sim_config.get("slippage_rate", slippage if slippage > 0 else 0.001),
        "limit_up_down": sim_config.get("limit_up_down", False),
        "t_plus_1": sim_config.get("t_plus_1", False),
        "min_trade_unit": sim_config.get("min_trade_unit", 100),
        "max_single_position": sim_config.get("max_single_position", 0.2),
        "stop_loss": sim_config.get("stop_loss", 0.15),
        "partial_fill": sim_config.get("partial_fill", False),
        "cash_t_plus_1": sim_config.get("cash_t_plus_1", False),
    }
    if sc['limit_up_down'] or sc['t_plus_1'] or sc['stop_loss'] or sc['partial_fill']:
        strategy_class._sim_config = sc
        strategy_class._sim_data = data
        strategy_class._sim_code = getattr(data, "name", "")
    # ---- 执行回测 ----
    bt = _Backtest(
        data, strategy_class, cash=cash, commission=commission,
        exclusive_orders=exclusive_orders, finalize_trades=True, **kwargs,
    )
    result = bt.run()
    # ---- 提取指标 ----
    metrics = extract_metrics(result._series if hasattr(result, "_series") else result)
    # ---- 实盘成本调整 ----
    if sc['slippage_rate'] > 0 or sc['stamp_duty_rate'] > 0 or sc['transfer_fee_rate'] > 0 or sc['min_commission'] > 5.0:
        cost_info = _calc_realistic_costs(result, sc)
        metrics["_real_costs"] = cost_info
        metrics["实盘年化收益率%"] = _adjust_return(metrics.get("年化收益%", 0), cost_info)
        risk_warnings["real_costs"] = cost_info
    else:
        metrics["实盘年化收益率%"] = metrics.get("年化收益%", 0)
    sim_report = _build_sim_report(sc)
    if sim_report:
        metrics["_sim_rules"] = sim_report
        risk_warnings["sim_rules"] = sim_report
    metrics["模拟配置"] = sc.get("limit_up_down", False) or sc.get("t_plus_1", False) or sc.get("stop_loss", False)
    # ---- 自动保存 ----
    if auto_save:
        _auto_save(result, metrics, risk_warnings, strategy_class, data, cash, commission, slippage, sim_config)
    return result, metrics, risk_warnings


def _calc_realistic_costs(result, sc):
    from engine.costs import calc_commission, calc_stamp_duty, calc_transfer_fee, calc_slippage
    trades = getattr(result, "_trades", None)
    import pandas as _pd
    if trades is None:
        return {"note": "无交易记录", "extra_cost": 0}
    total_extra = 0.0
    buy_fees = []
    sell_fees = []
    if isinstance(trades, _pd.DataFrame):
        items = list(trades.iterrows())
    else:
        items = list(enumerate(trades if hasattr(trades, "__iter__") else []))
    for idx_or_row, t in items:
        if isinstance(trades, _pd.DataFrame):
            shares = abs(t.get("Size", 0))
            if shares <= 0: continue
            side = "buy" if t.get("Size", 0) > 0 else "sell"
            price = abs(t.get("EntryPrice", 0) if side == "buy" else t.get("ExitPrice", 0))
        else:
            shares = abs(getattr(t, "size", 0))
            if shares <= 0: continue
            side = "buy" if getattr(t, "size", 0) > 0 else "sell"
            price = abs(getattr(t, "price", 0))
        if price <= 0: continue
        bt_comm = calc_commission(price, shares, sc.get("commission_rate", 0.0003), min_fee=0)
        real_comm = calc_commission(price, shares, sc.get("commission_rate", 0.0003), sc.get("min_commission", 5.0))
        extra_comm = real_comm - bt_comm
        stamp = calc_stamp_duty(price, shares, side == "sell", sc.get("stamp_duty_rate", 0.0005))
        trans = calc_transfer_fee(price, shares, sc.get("transfer_fee_rate", 0.00001))
        slip_price = calc_slippage(price, side, sc.get("slippage_rate", 0.001))
        slip_cost = abs(slip_price - price) * shares
        t_extra = max(0, extra_comm) + stamp + trans + slip_cost
        total_extra += t_extra
        if side == "buy":
            buy_fees.append(t_extra)
        else:
            sell_fees.append(t_extra)
    return {
        "extra_cost": round(total_extra, 2),
        "buy_count": len(buy_fees),
        "sell_count": len(sell_fees),
        "avg_buy_extra": round(sum(buy_fees) / len(buy_fees), 2) if buy_fees else 0,
        "avg_sell_extra": round(sum(sell_fees) / len(sell_fees), 2) if sell_fees else 0,
    }


def _adjust_return(base_return, cost_info):
    extra = cost_info.get("extra_cost", 0)
    if extra <= 0:
        return base_return
    return round(base_return - extra / 1000, 2)


def _build_sim_report(sc):
    items = []
    if sc['limit_up_down']: items.append("涨跌停")
    if sc['t_plus_1']: items.append("T+1")
    if sc['stop_loss']: items.append(f"最大回撤止损{sc.get('stop_loss',0.15):.0%}")
    if sc['partial_fill']: items.append("部分成交")
    if sc['cash_t_plus_1']: items.append("资金T+1可用")
    if sc['min_commission'] > 0: items.append(f"最低佣金{sc.get('min_commission',5.0)}元")
    if sc['stamp_duty_rate'] > 0: items.append(f"印花税{sc.get('stamp_duty_rate',0.0005):.4f}")
    if sc['transfer_fee_rate'] > 0: items.append(f"过户费{sc.get('transfer_fee_rate',0.00001):.5f}")
    if sc['slippage_rate'] > 0: items.append(f"滑点{sc.get('slippage_rate',0.001):.3f}")
    if items:
        return {"active_rules": items}
    return None


def run_optimize(strategy_class, data, cash=100000, commission=0.0003, maximize="Sharpe Ratio", constraint=None, **kwargs):
    bt = _Backtest(data, strategy_class, cash=cash, commission=commission)
    result = bt.optimize(maximize=maximize, constraint=constraint, **kwargs)
    return result


def _auto_save(result, metrics, risk, strategy_class, data, cash, commission, slippage=None, sim_config=None):
    from results.vault import save_run
    try:
        symbol = getattr(data, "name", "") or ""
        params = {}
        for attr in dir(strategy_class):
            if attr[0].isalpha() and not attr.startswith("_"):
                val = getattr(strategy_class, attr, None)
                if isinstance(val, (int, float, str, bool)):
                    params[attr] = val
        run_id = save_run(
            strategy_name=strategy_class.name,
            metrics=metrics,
            result=result,
            risk=risk,
            params=params,
            symbol=symbol, market="A",
            cash=cash, commission=commission, slippage=slippage or 0.0,
            sim_config=sim_config,
        )
    except Exception:
        pass