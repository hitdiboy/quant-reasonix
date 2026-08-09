import sys, os, json, duckdb, pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paper_trading.simulator import PaperSimulator


class PaperTracker:
    def __init__(self, db_path, top_n=10):
        self.db = duckdb.connect(db_path)
        self.sims = {}
        sql = """
            SELECT strategy_name, symbol, market, sharpe_ratio,
                   return_pct, max_drawdown_pct, num_trades
            FROM (
                SELECT strategy_name, symbol, market,
                       sharpe_ratio, return_pct, max_drawdown_pct, num_trades,
                       ROW_NUMBER() OVER (PARTITION BY strategy_name, symbol ORDER BY sharpe_ratio DESC) AS rn
                FROM backtest_runs
                WHERE sharpe_ratio > 0.5 AND max_drawdown_pct > -60 AND num_trades > 5
            ) s WHERE rn = 1
            ORDER BY sharpe_ratio DESC
            LIMIT ?
        """
        df = self.db.execute(sql, [top_n]).fetchdf()
        self.strategies = df
        for _, r in df.iterrows():
            key = f"{r.symbol}_{r.strategy_name[:40]}"
            self.sims[key] = PaperSimulator(cash=100000)


    def _parse_params(self, vname, sclass):
        keys = sorted(sclass.params.keys())
        cn = sclass.name or sclass.__name__
        rest = vname[len(cn)+1:]
        out = {}
        for k in keys:
            if not rest.startswith(k): break
            vs = rest[len(k):]
            i = vs.find('_')
            if i >= 0:
                vp, rest = vs[:i], vs[i+1:]
            else:
                vp, rest = vs, ''
            try: out[k] = int(vp) if '.' not in vp else float(vp)
            except: out[k] = vp
        return out

    def run(self):
        from data.fetch.unified import fetch
        from backtesting import Backtest
        from strategies.factory import StrategyFactory
        from strategies.ma_cross import MaCross
        from strategies.bollinger import BollingerBreakout
        from strategies.rsi_reversal import RsiReversal
        from strategies.momentum import Momentum
        from strategies.dual_momentum import DualMomentum
        from strategies.volatility_breakout import VolatilityBreakout
        from strategies.grid_trading import GridTrading
        from strategies.turtle_trading import TurtleTrading
        from strategies.channel_breakout import ChannelBreakout
        from strategies.bollinger_reversion import BollingerReversion
        from strategies.macd_strategy import MACDStrategy
        from strategies.triple_ma import TripleMA
        from strategies.mean_reversion import MeanReversion

        factory = StrategyFactory()
        for s in [MaCross, BollingerBreakout, RsiReversal, Momentum, DualMomentum,
                  VolatilityBreakout, GridTrading, TurtleTrading, ChannelBreakout,
                  BollingerReversion, MACDStrategy, TripleMA, MeanReversion]:
            factory.register(s)
        reg = factory._registry

        for _, row in self.strategies.iterrows():
            sym, sname = row.symbol, row.strategy_name
            cls_name = sname.split("_")[0] if sname else ""
            df = fetch(sym)
            if df is not None and len(df) > 100:
                df = df[df.index >= "2023-01-01"]
            if df is None or len(df) < 50:
                print(f"  {sym}: data insufficient ({len(df) if df is not None else 0})")
                continue
            target = reg.get(cls_name)
            if target is None:
                for n, c in reg.items():
                    if cls_name.lower() in n.lower():
                        target = c
                        break
            if target is None:
                print(f"  {sym}/{sname}: strategy class not found")
                continue
            params = self._parse_params(sname, target)
            for k, v in params.items():
                setattr(target, k, v)
            bt = Backtest(df, target, cash=100000, commission=0.0003, finalize_trades=True)
            result = bt.run()
            key = f"{sym}_{sname[:40]}"
            sim = self.sims.get(key)
            if not sim:
                continue
            if hasattr(result, "_trades") and result._trades is not None:
                td = result._trades
                if len(td) > 0:
                    for _, t in td.iterrows():
                        px, tm, sz = t["EntryPrice"], str(t["EntryTime"]), int(t["Size"])
                        if sz > 0:
                            sim.buy(tm, sym, px, sz)
                        else:
                            sim.sell(tm, sym, px, abs(sz))
                # Mark to market so equity is updated
                last_px = float(df['Close'].iloc[-1])
                sim.mark(str(df.index[-1]), {sym: last_px})

    def report(self):
        now = datetime.now().strftime("%Y-%m-%d")
        lines = [f"===== Paper Trading / {now} ====="]
        lines.append(f"  {'Strategy':>40s} {'Init':>10s} {'Current':>10s} {'Return%':>8s} {'Trades':>6s}")
        lines.append(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*8} {'-'*6}")
        for key, sim in sorted(self.sims.items(), key=lambda x: x[1].ret, reverse=True):
            i = sim.info()
            label = key[-38:]
            lines.append(f"  {label:>40s} {i['init']:>10,.0f} {i['final']:>10,.0f} {i['ret']:>+8.2f} {i['trades']:>6d}")
        return "\n".join(lines)

if __name__ == "__main__":
    db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results", "vault.db")
    t = PaperTracker(db, top_n=10)
    t.run()
    print(t.report())