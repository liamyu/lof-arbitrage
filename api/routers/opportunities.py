"""
机会列表路由
GET /api/v1/opportunities
"""
from typing import Optional
from fastapi import APIRouter, Query
from api.models import OpportunityListResponse, FundSignal
from core.analyzer import LOFArbitrageAnalyzer

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    min_score: int = Query(50, ge=0, le=100, description="最低评分阈值"),
    purchase_open: bool = Query(False, description="是否只返回可申购的"),
    max_fee: float = Query(0.5, ge=0, le=5, description="最大手续费百分比"),
    min_purchase_limit: float = Query(1000, ge=0, description="最小申购限额（元）"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制")
):
    """
    获取套利机会列表，按评分降序排列
    支持硬性过滤：申购状态、手续费、限额
    """
    analyzer = LOFArbitrageAnalyzer()
    signals = analyzer.get_opportunities(
        min_score=min_score,
        purchase_open=purchase_open,
        max_fee=max_fee,
        min_purchase_limit=min_purchase_limit
    )

    # 限制返回数量
    signals = signals[:limit]

    return OpportunityListResponse(
        data=signals,
        count=len(signals),
        filters={
            "min_score": min_score,
            "purchase_open": purchase_open,
            "max_fee": max_fee,
            "min_purchase_limit": min_purchase_limit,
            "limit": limit
        }
    )
