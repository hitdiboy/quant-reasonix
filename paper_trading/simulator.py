# 模拟交易引擎
import pandas as pd

class PaperSimulator:
    def __init__(self, cash=100000):
        self.init=cash; self.cash=cash; self.pos={}
        self.trades=[]; self.log=[]; self._eq=cash

    def buy(self, dt, sym, px, sh=0):
        mx=int(self.cash//px) if self.cash>0 else 0
        if mx==0: return
        if sh==0 or sh>mx: sh=mx
        cost=px*sh; self.cash-=cost
        if sym in self.pos:
            o=self.pos[sym]; ts=o["shares"]+sh; tc=o["shares"]*o["avg"]+cost
            self.pos[sym]={"shares":ts,"avg":round(tc/ts,2)}
        else: self.pos[sym]={"shares":sh,"avg":round(px,2)}
        self.trades.append({"dt":str(dt),"sym":sym,"side":"buy","sh":sh,"px":px,"pnl":0})

    def sell(self, dt, sym, px, sh=0):
        if sym not in self.pos: return
        p=self.pos[sym]
        if sh==0 or sh>p["shares"]: sh=p["shares"]
        rev=px*sh; pnl=round(rev-p["avg"]*sh,2); self.cash+=rev
        r=p["shares"]-sh
        if r<=0: del self.pos[sym]
        else: self.pos[sym]={"shares":r,"avg":p["avg"]}
        self.trades.append({"dt":str(dt),"sym":sym,"side":"sell","sh":sh,"px":px,"pnl":pnl})

    def mark(self, dt, px={}):
        pv=sum(p["shares"]*px.get(s,p["avg"]) for s,p in self.pos.items())
        t=round(self.cash+pv,2); self._eq=t
        self.log.append({"dt":str(dt),"cash":round(self.cash,2),"pos":round(pv,2),"total":t})

    @property
    def eq(self): return self._eq

    @property
    def ret(self):
        return round((self._eq/self.init-1)*100,2) if self.init>0 else 0.0

    def info(self):
        return {"init":self.init,"final":round(self._eq,2),"ret":self.ret,
                "trades":len(self.trades),"open":len(self.pos)}