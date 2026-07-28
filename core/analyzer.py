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
                "申购状态": "purchase_status",
                "赎回状态": "redeem_status",
                "日累计限定金额": "purchase_limit",
                "手续费": "fee_pct"
            }, inplace=True)
            fund_purchase_df["code"] = fund_purchase_df["code"].astype(str)
            return (
                fund_purchase_df
                .set_index("code")[[
                    "fund_name",
                    "purchase_status",
                    "redeem_status",
                    "purchase_limit",
                    "fee_pct"
                ]]
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

    def score_one_lof(self, lof_data: Dict[str, pd.DataFrame], code: str) -> Dict[str, Any]:
        """对单个 LOF 进行评分"""
        if code not in lof_data:
            return {
                "code": code,
                "score": 0,
                "signal": "无数据",
                "current_premium": None,
                "current_volume": None,
                "price_pct": None,
                "key_metrics": {},
                "reasons": {"plus": [], "minus": ["无数据"]}
            }

        df = lof_data[code].copy()
        recent = df.tail(30)

        current = recent.iloc[-1]
        cur_premium = current["discount_rt"]
        cur_volume = current.get("volume", 0)
        cur_pct = current.get("price_pct", 0)

        stats7 = self.premium_stats(df, 5)
        stats14 = self.premium_stats(df, 10)
        stats21 = self.premium_stats(df, 15)

        plus, minus = [], []

        # ================= 溢价率维度 =================
        premium_score = 0

        if cur_premium is None or pd.isna(cur_premium):
            minus.append("当日溢价率缺失，无法进一步分析")
        elif cur_premium < 0:
            minus.append("当前为折价，不适用溢价套利策略")
        else:
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

        return {
            "code": code,
            "score": total_score,
            "signal": score_to_signal(total_score),
            "current_premium": cur_premium,
            "current_volume": cur_volume,
            "price_pct": cur_pct,
            "key_metrics": {
                "premium_3d": recent["discount_rt"].tail(3).mean(),
                "premium_5d": recent["discount_rt"].tail(5).mean()
            },
            "reasons": {
                "plus": plus,
                "minus": minus
            }
        }

    def get_all_signals(self) -> List[Dict[str, Any]]:
        """获取所有 LOF 的套利信号（无 Streamlit 缓存依赖）"""
        lof_data = self.load_all_data()
        purchase_info_map = self.load_purchase_info()

        signals = []
        for code in lof_data:
            s = self.score_one_lof(lof_data, code)
            purchase_info = purchase_info_map.get(code, {})
            s["purchase_info"] = {
                "fund_name": purchase_info.get("fund_name"),
                "purchase_status": purchase_info.get("purchase_status"),
                "redeem_status": purchase_info.get("redeem_status"),
                "purchase_limit": purchase_info.get("purchase_limit"),
                "fee_pct": purchase_info.get("fee_pct")
            }
            # 添加数据时间戳
            s["data_as_of"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
            s["is_estimated"] = True  # 盘中估值，非确认净值
            signals.append(s)

        return sorted(signals, key=lambda x: x["score"], reverse=True)

    def get_opportunities(self, min_score: int = 50, purchase_open: bool = False,
                          max_fee: float = 0.5, min_purchase_limit: float = 1000) -> List[Dict[str, Any]]:
        """
        获取套利机会列表（API 友好接口）
        :param min_score: 最低评分阈值
        :param purchase_open: 是否只返回可申购的
        :param max_fee: 最大手续费百分比（默认 0.5%）
        :param min_purchase_limit: 最小申购限额（默认 1000 元）
        """
        signals = self.get_all_signals()
        filtered = [s for s in signals if s["score"] >= min_score]

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

    def get_fund_detail(self, code: str) -> Optional[Dict[str, Any]]:
        """获取单个基金详情（API 友好接口）"""
        lof_data = self.load_all_data()
        if code not in lof_data:
            return None

        df = lof_data[code]
        signal = self.score_one_lof(lof_data, code)

        # 补充申购信息
        purchase_info_map = self.load_purchase_info()
        purchase_info = purchase_info_map.get(code, {})
        signal["purchase_info"] = {
            "fund_name": purchase_info.get("fund_name"),
            "purchase_status": purchase_info.get("purchase_status"),
            "redeem_status": purchase_info.get("redeem_status"),
            "purchase_limit": purchase_info.get("purchase_limit"),
            "fee_pct": purchase_info.get("fee_pct")
        }
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
