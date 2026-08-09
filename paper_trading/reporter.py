import pandas as pd

class PerformanceReporter:
    @staticmethod
    def text(s):
        i=s.info()
        return (f"===== 模拟交易报告 =====\n"
                f"  初始资金: {i['init']:,.0f}\n"
                f"  最终权益: {i['final']:,.0f}\n"
                f"  收益率:   {i['ret']:+.2f}%\n"
                f"  交易次数: {i['trades']}\n"
                f"  当前持仓: {i['open']} 个")

    @staticmethod
    def equity(s):
        if not s.log: return pd.DataFrame()
        df=pd.DataFrame(s.log)
        df["dt"]=pd.to_datetime(df["dt"])
        return df.set_index("dt")