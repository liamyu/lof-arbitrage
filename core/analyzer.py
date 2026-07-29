"""
LOF 套利评分分析器（纯数据服务，无 UI 依赖）
从 LOF_dashboard.py 中提取的纯逻辑评分引擎
"""
import os
import warnings
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def is_monotonic_increasing(arr):
    return all(arr[i] < arr[i + 1] for i in range(len(arr) - 1))


def is_monotonic_decreasing(arr):
    return all(arr[i] > arr[i + 1] for i in range(len(arr) - 1))


def now_cn():
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def is_pre_order_time():
    now = now_cn().time()
    return time(9, 30) <= now <= time(14, 00)


def score_to_signal(score: int) -> str:
    """将分数转换为信号标签（避免"胜率"措辞，改用"评分等级"）"""
    if score >= 80:
        return "评分优秀"
    elif score >= 65:
        return "评分良好"
    elif score >= 50:
        return "评分中等"
    elif score >= 35:
        return "评分一般"
    else:
        return "不推荐"


def parse_purchase_limit(limit_val) -> float:
    """解析申购限额，返回实际金额（元），无法解析返回 0"""
    if limit_val is None or pd.isna(limit_val):
        return 0
    if isinstance(limit_val, (int, float)):
        return float(limit_val)
    # 处理字符串如 "限购100万"
    s = str(limit_val).strip()
    if s in ("", "--", "-", "无限制"):
        return float('inf')
    try:
        return float(s)
    except ValueError:
        return 0


def is_purchase_open(status: Optional[str], limit: float = 0) -> bool:
    """判断是否可申购"""
    if not status:
        return False
    status = str(status).strip()
    blocked_keywords = ("暂停申购", "封闭期", "认购期", "停止申购", "限购0")
    if any(k in status for k in blocked_keywords):
        return False
    if limit == 0:
        return False
    return True


def get_purchase_block_reason(status: Optional[str], fee_pct: Optional[float],
                               limit: float, max_fee: float = 0.5,
                               min_limit: float = 1000) -> Optional[str]:
    """
    获取申购阻断原因。返回 None 表示可通过硬性过滤。
    """
    if not status:
        return "无申购状态信息"
    status = str(status).strip()
    blocked_keywords = ("暂停申购", "封闭期", "认购期", "停止申购")
    if any(k in status for k in blocked_keywords):
        return f"申购状态: {status}"
    if "限购0" in status or limit == 0:
        return "日申购限额为 0"
    if limit < min_limit:
        return f"日申购限额过低 ({limit:.0f} 元)"
    if fee_pct is not None and fee_pct > max_fee:
        return f"手续费过高 ({fee_pct}%)"
    return None


def estimate_redeem_fee(purchase_info: Optional[Dict[str, Any]],
                        holding_days: int = 7) -> float:
    """
    估计赎回费率（%）。
    由于数据源通常不提供赎回费率，采用分档默认估计：
    - 持有 <7 天: 1.50%（监管上限）
    - 持有 7-30 天: 0.75%（常见档）
    - 持有 30-365 天: 0.50%
    - 持有 >365 天: 0.25%
    LOF 溢价套利 T+2 到账即卖出，不涉及赎回费；
    折价套利若采用买入+赎回策略，持有期通常很短（<7 天）。
    """
    if holding_days < 7:
        return 1.50
    elif holding_days < 30:
        return 0.75
    elif holding_days < 365:
        return 0.50
    else:
        return 0.25


def calculate_premium_net_profit(cur_premium: float, fee_pct: Optional[float],
                                  trade_commission: float = 0.025) -> float:
    """
    计算溢价套利净利润（%）。
    公式: 溢价率 - 申购费 - 交易佣金（卖出）
    """
    fee = fee_pct if fee_pct is not None and not pd.isna(fee_pct) else 1.50
    net = cur_premium - fee - trade_commission
    return round(net, 2)


def calculate_discount_net_profit(abs_discount: float, redeem_fee: float,
                                   trade_commission: float = 0.025) -> float:
    """
    计算折价套利净利润（%）。
    公式: |折价率| - 赎回费 - 交易佣金（买入）
    """
    net = abs_discount - redeem_fee - trade_commission
    return round(net, 2)


def net_profit_to_signal(net_profit: float) -> str:
    """净利润等级标签"""
    if net_profit >= 3:
        return "利润充足"
    elif net_profit >= 1:
        return "利润微薄"
    elif net_profit > 0:
        return "薄利边缘"
    elif net_profit > -1:
        return "基本无利"
    else:
        return "亏损风险"


def is_qdii_fund(fund_type: Optional[str]) -> bool:
    """判断是否为 QDII 基金"""
    if not fund_type:
        return False
    return "QDII" in str(fund_type).upper() or "qdii" in str(fund_type).lower()


def calculate_t2_risk(df: pd.DataFrame, direction: str = "premium") -> Optional[float]:
    """
    计算 T+2 等待期风险（历史最大 2 日回撤）。
    :param direction: 'premium' 或 'discount'，用于确定回撤方向
    :return: 历史最大 2 日回撤（%），正数表示不利变动幅度
    """
    recent = df.tail(60).copy()
    valid = recent.dropna(subset=["discount_rt"])
    if len(valid) < 10:
        return None

    rates = valid["discount_rt"].values
    max_adverse = 0.0

    for i in range(len(rates) - 2):
        start = rates[i]
        # T+2 期间（后续2个交易日）的极端值
        window = rates[i + 1:i + 3]

        if direction == "premium":
            # 溢价套利：不利变动 = 溢价率下降（下跌）
            # 从 start 到 window 最低点的跌幅
            if start > 0:
                end_low = window.min()
                adverse = start - end_low
                if adverse > max_adverse:
                    max_adverse = adverse
        else:
            # 折价套利：不利变动 = 折价率收敛（绝对值下降）
            # 从 |start| 到 window 中绝对值最低点的收敛幅度
            abs_start = abs(start)
            if abs_start > 0:
                abs_window = np.abs(window)
                end_low = abs_window.min()
                adverse = abs_start - end_low
                if adverse > max_adverse:
                    max_adverse = adverse

    return round(max_adverse, 2) if max_adverse > 0 else None


def get_project_root() -> str:
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    return os.path.dirname(current_dir)


def get_cache_path(project_root: str) -> Optional[str]:
    data_dir = os.path.join(project_root, "data")
    if not os.path.exists(data_dir):
        return None
    for fname in os.listdir(data_dir):
        if fname.startswith("fund_purchase_em_") and fname.endswith(".csv"):
            return os.path.join(data_dir, fname)
    return None


class LOFArbitrageAnalyzer:
    """LOF 套利评分分析器（无 Streamlit 依赖）"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self._lof_data: Optional[Dict[str, pd.DataFrame]] = None
        self._purchase_info: Optional[Dict[str, dict]] = None

    def load_all_data(self) -> Dict[str, pd.DataFrame]:
        """加载所有 LOF 数据（无缓存装饰器，由调用方决定是否缓存）"""
        project_root = get_project_root()
        data_dir_path = os.path.join(project_root, self.data_dir)

        csv_files = [f for f in os.listdir(data_dir_path)
                     if f.startswith('lof_') and f.endswith('.csv')]
        lof_data = {}
        for file in csv_files:
            code = file.replace('lof_', '').replace('.csv', '')
            file_path = os.path.join(data_dir_path, file)
            try:
                df = pd.read_csv(file_path, dtype=str)
                df['price_dt'] = pd.to_datetime(df['price_dt'], errors='coerce')

                # 数值列统一转换
                numeric_cols = ['price', 'net_value', 'est_val', 'discount_rt', 'volume', 'amount', 'amount_incr']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                df["price_pct"] = df["price"].pct_change() * 100

                # 用估值回填缺失的溢价率
                if 'est_val' in df.columns and 'discount_rt' in df.columns:
                    mask = df['discount_rt'].isna() & df['est_val'].notna() & df['est_val'] != 0
                    df.loc[mask, 'discount_rt'] = ((df.loc[mask, 'price'] / df.loc[mask, 'est_val'] - 1) * 100).round(2)

                df = df.dropna(subset=['price_dt'])
                if not df.empty:
                    lof_data[code] = df.sort_values('price_dt').reset_index(drop=True)
            except Exception as e:
                print(f"加载 {code} 数据失败: {e}")
        return lof_data

    def load_purchase_info(self) -> Dict[str, dict]:
        """加载基金申购信息"""
        project_root = get_project_root()
        cache_path = get_cache_path(project_root)

        if cache_path is None or not os.path.exists(cache_path):
            return {}

        try:
            fund_purchase_df = pd.read_csv(cache_path, dtype={"基金代码": str})
            fund_purchase_df.rename(columns={
                "基金代码": "code",
                "基金简称": "fund_name",
                "基金类型": "fund_type",
                "申购状态": "purchase_status",
                "赎回状态": "redeem_status",
                "日累计限定金额": "purchase_limit",
                "手续费": "fee_pct"
            }, inplace=True)
            fund_purchase_df["code"] = fund_purchase_df["code"].astype(str)
            cols = ["fund_name", "fund_type", "purchase_status",
                    "redeem_status", "purchase_limit", "fee_pct"]
            # 过滤掉 CSV 中不存在的列
            cols = [c for c in cols if c in fund_purchase_df.columns]
            return (
                fund_purchase_df
                .set_index("code")[cols]
                .to_dict(orient="index")
            )
        except Exception as e:
            print(f"加载申购信息失败: {e}")
            return {}

    def premium_stats(self, df: pd.DataFrame, days: int) -> Dict[str, float]:
        d = df.tail(days)
        return {
            "mean": d["discount_rt"].mean(),
            "std": d["discount_rt"].std()
        }

    def score_one_lof(self, lof_data: Dict[str, pd.DataFrame], code: str,
                       purchase_info: Optional[Dict[str, Any]] = None,
                       trade_commission: float = 0.025) -> Dict[str, Any]:
        """
        对单个 LOF 进行评分，并计算净利润。
        :param trade_commission: 交易佣金率（单边，默认 0.025%，即万 2.5）
        """
        if code not in lof_data:
            return {
                "code": code,
                "score": 0,
                "signal": "无数据",
                "current_premium": None,
                "current_volume": None,
                "price_pct": None,
                "key_metrics": {},
                "reasons": {"plus": [], "minus": ["无数据"]},
                "net_profit": None,
                "net_profit_signal": None,
                "cost_breakdown": None,
                "arbitrage_direction": None,
                "is_qdii": False
            }

        df = lof_data[code].copy()
        recent = df.tail(30)

        current = recent.iloc[-1]
        cur_premium = current["discount_rt"]
        cur_volume = current.get("volume", 0)
        cur_pct = current.get("price_pct", 0)

        # 获取申购信息
        fee_pct = None
        fund_type = None
        if purchase_info:
            fee_pct = purchase_info.get("fee_pct")
            fund_type = purchase_info.get("fund_type")

        # QDII 识别
        qdii = is_qdii_fund(fund_type)

        stats7 = self.premium_stats(df, 5)
        stats14 = self.premium_stats(df, 10)
        stats21 = self.premium_stats(df, 15)

        # 为折价套利准备绝对值统计
        abs_series = recent["discount_rt"].abs()
        stats7_abs = {"mean": abs_series.tail(5).mean(), "std": abs_series.tail(5).std()}
        stats14_abs = {"mean": abs_series.tail(10).mean(), "std": abs_series.tail(10).std()}
        stats21_abs = {"mean": abs_series.tail(15).mean(), "std": abs_series.tail(15).std()}

        plus, minus = [], []

        # ================= 溢价率/折价率维度 =================
        premium_score = 0

        # 净利润计算（无论溢价/折价都计算）
        net_profit = None
        cost_breakdown = None
        arbitrage_direction = None

        if cur_premium is None or pd.isna(cur_premium):
            minus.append("当日溢价率缺失，无法进一步分析")
        elif cur_premium < 0:
            # ================= 折价套利评分 =================
            abs_discount = abs(cur_premium)

            premium_score += 60 if abs_discount >= 5 else int(abs_discount * 10)

            if abs_discount > stats7_abs["mean"] + stats7_abs["std"]:
                premium_score += 5
                plus.append("当前折价率显著高于5日均值，折价空间扩大")

            if abs_discount - stats14_abs["mean"] > stats14_abs["std"] * 1.5:
                premium_score += 5
                plus.append("当前折价率显著高于10日均值")

            if abs_discount - stats21_abs["mean"] > stats21_abs["std"] * 2:
                premium_score += 5
                plus.append("当前折价率显著高于15日均值")

            if 10 <= abs_discount < 20:
                premium_score += 10
                plus.append("当前折价率处于10-20%，套利空间充足")
            elif abs_discount >= 20:
                premium_score += 20
                plus.append("当前折价率 >=20%，属于极端折价空间")

            last3_abs = abs_series.tail(3).values

            if (last3_abs >= 5).all() and is_monotonic_increasing(last3_abs):
                premium_score += 15
                plus.append("近3日折价率均 >=5%且逐日扩大，套利空间稳步扩张")
            elif (last3_abs >= 5).all():
                premium_score += 10
                plus.append("近3日折价率均 >=5%，套利空间稳定存在")
            elif (last3_abs >= 3).all():
                premium_score += 5
                plus.append("近3日折价率维持在3%-5%，具备折价套利基础")

            if is_monotonic_decreasing(last3_abs):
                premium_score -= 10
                minus.append("折价率近3日逐日收敛，短期套利窗口缩小")
            elif abs_series.iloc[-1] < abs_series.iloc[-2]:
                premium_score -= 5
                minus.append("折价率较昨日有所收敛，短期套利动能减弱")

            # 价格暴涨会缩小折价，对套利不利
            if cur_pct >= 9.5:
                premium_score -= 20
                minus.append("场内价格接近涨停，折价可能快速收敛，套利风险极高")
            elif cur_pct >= 8:
                premium_score -= 15
                minus.append("场内价格涨超8%，折价稳定性存疑")
            elif cur_pct >= 5:
                premium_score -= 10
                minus.append("场内价格涨超5%，需防止折价快速收敛")

            # 折价套利净利润
            redeem_fee = estimate_redeem_fee(purchase_info, holding_days=2)
            net_profit = calculate_discount_net_profit(
                abs_discount, redeem_fee, trade_commission
            )
            cost_breakdown = {
                "gross_spread": round(abs_discount, 2),
                "redeem_fee": redeem_fee,
                "trade_commission": trade_commission,
                "purchase_fee": 0,
                "total_cost": round(redeem_fee + trade_commission, 3),
                "note": "折价套利：买入场内 + 赎回"
            }
            arbitrage_direction = "discount"
        else:
            # ================= 溢价套利评分 =================
            premium_score += 60 if cur_premium >= 5 else int(cur_premium * 10)

            if cur_premium > stats7["mean"] + stats7["std"]:
                premium_score += 5
                plus.append("当前溢价率显著高于5日均值")

            if cur_premium - stats14["mean"] > stats14["std"] * 1.5:
                premium_score += 5
                plus.append("当前溢价率显著高于10日均值")

            if cur_premium - stats21["mean"] > stats21["std"] * 2:
                premium_score += 5
                plus.append("当前溢价率显著高于15日均值")

            if 10 <= cur_premium < 20:
                premium_score += 10
                plus.append("当前溢价率处于10-20%，套利空间充足")
            elif cur_premium >= 20:
                premium_score += 20
                plus.append("当前溢价率 >=20%，属于极端溢价空间")

            last3 = recent["discount_rt"].tail(3).values

            if (last3 >= 5).all() and is_monotonic_increasing(last3):
                premium_score += 15
                plus.append("近3日溢价率均 >=5%且逐日上升，套利空间稳步扩张")
            elif (last3 >= 5).all():
                premium_score += 10
                plus.append("近3日溢价率均 >=5%，套利空间稳定存在")
            elif (last3 >= 3).all():
                premium_score += 5
                plus.append("近3日溢价率维持在3%-5%，具备溢价套利基础")

            if is_monotonic_decreasing(last3):
                premium_score -= 10
                minus.append("溢价率近3日逐日下降，短期套利窗口收敛")
            elif recent["discount_rt"].iloc[-1] < recent["discount_rt"].iloc[-2]:
                premium_score -= 5
                minus.append("溢价率较昨日有所下滑，短期套利动能减弱")

            if cur_pct <= -9.5:
                premium_score -= 20
                minus.append("场内价格接近跌停，情绪化抛压显著，套利风险极高")
            elif cur_pct <= -8:
                premium_score -= 15
                minus.append("场内价格跌超8%，恐慌性下跌阶段，溢价稳定性存疑")
            elif cur_pct <= -5:
                premium_score -= 10
                minus.append("场内价格跌超5%，短期情绪偏弱，需防止溢价快速回落")

            # 溢价套利净利润
            net_profit = calculate_premium_net_profit(
                cur_premium, fee_pct, trade_commission
            )
            fee = fee_pct if fee_pct is not None and not pd.isna(fee_pct) else 1.50
            cost_breakdown = {
                "gross_spread": round(cur_premium, 2),
                "purchase_fee": fee,
                "trade_commission": trade_commission,
                "redeem_fee": 0,
                "total_cost": round(fee + trade_commission, 3),
                "note": "溢价套利：申购 + 场内卖出"
            }
            arbitrage_direction = "premium"

        premium_score = max(0, 0.6 * min(100, premium_score))

        # ================= 流动性维度 =================
        liquidity_score = 0

        if is_pre_order_time():
            liquidity_window = recent.iloc[-4:-1]
        else:
            liquidity_window = recent.iloc[-3:]

        if len(liquidity_window) == 3 and \
                (liquidity_window["volume"] >= 1000).all() and \
                (liquidity_window["amount"] >= 1000).all():
            liquidity_score += 60
            plus.append("近3日成交额均 >=1000万元，场内份额均 >=1000万份，具备套利执行基础")

            amount_incr_today = current.get("amount_incr", 0)
            last3_amount_incr = recent["amount_incr"].tail(3).values

            if abs(amount_incr_today) < 1:
                liquidity_score += 5
                plus.append("当日场内份额增速绝对值 <1%，套利盘未明显集中进出")

            if (np.abs(last3_amount_incr) < 1).all():
                liquidity_score += 15
                plus.append("近3日份额增速绝对值均 <1%，份额结构高度稳定")

            last3_premium = recent["discount_rt"].tail(3).values
            if amount_incr_today > 3 and is_monotonic_decreasing(last3_premium):
                liquidity_score -= 20
                minus.append("当日场内份额增速 >3% 且溢价率连续回落，套利盘加速撤离")
        else:
            minus.append("近3日成交额或场内份额不足，存在较大的流动性风险，套利需谨慎")

        liquidity_score = max(0, 0.5 * min(80, liquidity_score))

        total_score = int(premium_score + liquidity_score)

        # 净利润信号
        net_signal = net_profit_to_signal(net_profit) if net_profit is not None else None

        # T+2 风险量化
        t2_risk = calculate_t2_risk(df, direction=arbitrage_direction or "premium")

        # QDII 到账周期风险调整
        if qdii and net_profit is not None and net_profit > 0:
            qdii_penalty = 10
            total_score = max(0, total_score - qdii_penalty)
            minus.append("QDII 基金到账周期更长（T+3+），套利风险高于普通 LOF，评分已扣减")

        # T+2 风险调整：如果净利润不足以覆盖历史最大 2 日回撤，额外扣分
        if t2_risk is not None and net_profit is not None and net_profit > 0:
            if net_profit < t2_risk:
                t2_penalty = min(15, int((t2_risk - net_profit) * 5))
                total_score = max(0, total_score - t2_penalty)
                minus.append(f"净利润({net_profit:.2f}%)不足以覆盖历史T+2最大回撤({t2_risk:.2f}%)，评分已扣减")
            else:
                plus.append(f"净利润覆盖历史T+2最大回撤({t2_risk:.2f}%)，风险可控")

        return {
            "code": code,
            "score": total_score,
            "signal": score_to_signal(total_score),
            "current_premium": cur_premium,
            "current_volume": cur_volume,
            "price_pct": cur_pct,
            "key_metrics": {
                "premium_3d": recent["discount_rt"].tail(3).mean(),
                "premium_5d": recent["discount_rt"].tail(5).mean(),
                "t2_risk": t2_risk
            },
            "reasons": {
                "plus": plus,
                "minus": minus
            },
            "net_profit": net_profit,
            "net_profit_signal": net_signal,
            "cost_breakdown": cost_breakdown,
            "arbitrage_direction": arbitrage_direction,
            "is_qdii": qdii
        }

    def _build_purchase_info(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """统一组装 purchase_info 结构"""
        return {
            "fund_name": raw.get("fund_name"),
            "fund_type": raw.get("fund_type"),
            "purchase_status": raw.get("purchase_status"),
            "redeem_status": raw.get("redeem_status"),
            "purchase_limit": raw.get("purchase_limit"),
            "fee_pct": raw.get("fee_pct")
        }

    def get_all_signals(self, trade_commission: float = 0.025) -> List[Dict[str, Any]]:
        """获取所有 LOF 的套利信号（无 Streamlit 缓存依赖）"""
        lof_data = self.load_all_data()
        purchase_info_map = self.load_purchase_info()

        signals = []
        for code in lof_data:
            purchase_info = purchase_info_map.get(code, {})
            s = self.score_one_lof(lof_data, code,
                                    purchase_info=purchase_info,
                                    trade_commission=trade_commission)
            s["purchase_info"] = self._build_purchase_info(purchase_info)
            # 添加数据时间戳
            s["data_as_of"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
            s["is_estimated"] = True  # 盘中估值，非确认净值
            signals.append(s)

        return sorted(signals, key=lambda x: x["score"], reverse=True)

    def get_opportunities(self, min_score: int = 50, purchase_open: bool = False,
                          max_fee: float = 0.5, min_purchase_limit: float = 1000,
                          trade_commission: float = 0.025,
                          min_net_profit: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        获取套利机会列表（API 友好接口）
        :param min_score: 最低评分阈值
        :param purchase_open: 是否只返回可申购的
        :param max_fee: 最大手续费百分比（默认 0.5%）
        :param min_purchase_limit: 最小申购限额（默认 1000 元）
        :param trade_commission: 交易佣金率（单边，默认 0.025%）
        :param min_net_profit: 最低净利润阈值（默认 None 不启用）
        """
        signals = self.get_all_signals(trade_commission=trade_commission)
        filtered = [s for s in signals if s["score"] >= min_score]

        if min_net_profit is not None:
            filtered = [
                s for s in filtered
                if s.get("net_profit") is not None and s["net_profit"] >= min_net_profit
            ]

        if purchase_open:
            result = []
            for s in filtered:
                p = s.get("purchase_info", {})
                status = p.get("purchase_status")
                fee_pct = p.get("fee_pct")
                limit = parse_purchase_limit(p.get("purchase_limit"))

                block_reason = get_purchase_block_reason(
                    status, fee_pct, limit,
                    max_fee=max_fee, min_limit=min_purchase_limit
                )
                if block_reason is None:
                    result.append(s)
                else:
                    # 标记被过滤原因，用于调试
                    s["_block_reason"] = block_reason
            filtered = result

        return filtered

    def get_fund_detail(self, code: str,
                         trade_commission: float = 0.025) -> Optional[Dict[str, Any]]:
        """获取单个基金详情（API 友好接口）"""
        lof_data = self.load_all_data()
        if code not in lof_data:
            return None

        df = lof_data[code]
        purchase_info_map = self.load_purchase_info()
        purchase_info = purchase_info_map.get(code, {})
        signal = self.score_one_lof(lof_data, code,
                                     purchase_info=purchase_info,
                                     trade_commission=trade_commission)

        signal["purchase_info"] = self._build_purchase_info(purchase_info)
        signal["data_as_of"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
        signal["is_estimated"] = True

        # 历史数据摘要
        history_summary = {
            "latest_price": float(df["price"].iloc[-1]) if "price" in df.columns else None,
            "latest_net_value": float(df["net_value"].iloc[-1]) if "net_value" in df.columns else None,
            "latest_est_val": float(df["est_val"].iloc[-1]) if "est_val" in df.columns else None,
            "record_count": len(df),
            "date_range": {
                "start": df["price_dt"].min().strftime("%Y-%m-%d"),
                "end": df["price_dt"].max().strftime("%Y-%m-%d")
            }
        }

        signal["history_summary"] = history_summary
        return signal
