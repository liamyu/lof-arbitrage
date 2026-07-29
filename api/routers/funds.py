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
from core.analyzer import get_analyzer, get_project_root

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("/{code}", response_model=FundDetail)
def get_fund_detail(
    code: str,
    trade_commission: float = Query(0.020, ge=0, le=1, description="交易佣金率（单边，默认 0.020%）")
):
    """
    获取单个基金的详细信息
    """
    analyzer = get_analyzer()
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
    获取单个基金的评分（短路优化：不加载全量数据）
    """
    analyzer = get_analyzer()
    signal = analyzer.get_fund_score_standalone(code, trade_commission=trade_commission)

    if signal is None:
        raise HTTPException(status_code=404, detail=f"基金 {code} 未找到")

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
