"""
基金详情路由
GET /api/v1/funds/{code}
GET /api/v1/funds/{code}/history
GET /api/v1/funds/{code}/score
"""
import os
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import List
from api.models import FundDetail, FundSignal, FundHistoryResponse, FundHistoryRecord
from core.analyzer import LOFArbitrageAnalyzer, get_project_root

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("/{code}", response_model=FundDetail)
def get_fund_detail(
    code: str,
    trade_commission: float = Query(0.020, ge=0, le=1, description="交易佣金率（单边，默认 0.020%）")
):
    """
    获取单个基金的详细信息
    """
    analyzer = LOFArbitrageAnalyzer()
    detail = analyzer.get_fund_detail(code, trade_commission=trade_commission)

    if detail is None:
        raise HTTPException(status_code=404, detail=f"基金 {code} 未找到")

    return detail


@router.get("/{code}/score", response_model=FundSignal)
def get_fund_score(
    code: str,
    trade_commission: float = Query(0.020, ge=0, le=1, description="交易佣金率（单边，默认 0.020%）")
):
    """
    获取单个基金的评分
    """
    analyzer = LOFArbitrageAnalyzer()
    lof_data = analyzer.load_all_data()
    purchase_info_map = analyzer.load_purchase_info()

    if code not in lof_data:
        raise HTTPException(status_code=404, detail=f"基金 {code} 未找到")

    purchase_info = purchase_info_map.get(code, {})
    signal = analyzer.score_one_lof(lof_data, code,
                                     purchase_info=purchase_info,
                                     trade_commission=trade_commission)

    # 补充申购信息
    signal["purchase_info"] = {
        "fund_name": purchase_info.get("fund_name"),
        "fund_type": purchase_info.get("fund_type"),
        "purchase_status": purchase_info.get("purchase_status"),
        "redeem_status": purchase_info.get("redeem_status"),
        "purchase_limit": purchase_info.get("purchase_limit"),
        "fee_pct": purchase_info.get("fee_pct")
    }
    from datetime import datetime
    from zoneinfo import ZoneInfo
    signal["data_as_of"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    signal["is_estimated"] = True

    return signal


@router.get("/{code}/history", response_model=FundHistoryResponse)
def get_fund_history(
    code: str,
    days: int = Query(60, ge=1, le=365, description="返回最近多少天的数据")
):
    """
    获取单个基金的历史行情数据
    """
    project_root = get_project_root()
    file_path = os.path.join(project_root, "data", f"lof_{code}.csv")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"基金 {code} 历史数据未找到")

    try:
        df = pd.read_csv(file_path)
        df['price_dt'] = pd.to_datetime(df['price_dt'])
        df = df.sort_values('price_dt').tail(days)

        records = []
        for _, row in df.iterrows():
            records.append(FundHistoryRecord(
                date=row['price_dt'].strftime("%Y-%m-%d"),
                price=_safe_float(row, 'price'),
                net_value=_safe_float(row, 'net_value'),
                est_val=_safe_float(row, 'est_val'),
                discount_rt=_safe_float(row, 'discount_rt'),
                volume=_safe_float(row, 'volume'),
                amount=_safe_float(row, 'amount')
            ))

        return FundHistoryResponse(
            code=code,
            records=records,
            days=len(records)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取历史数据失败: {str(e)}")


def _safe_float(row, col):
    """安全地获取浮点数值"""
    try:
        val = row.get(col)
        if pd.isna(val):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None
