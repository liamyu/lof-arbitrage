"""
Pydantic 数据模型
定义 API 的请求/响应结构
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PurchaseInfo(BaseModel):
    fund_name: Optional[str] = None
    purchase_status: Optional[str] = None
    redeem_status: Optional[str] = None
    purchase_limit: Optional[float] = None
    fee_pct: Optional[float] = None


class KeyMetrics(BaseModel):
    premium_3d: Optional[float] = None
    premium_5d: Optional[float] = None


class Reasons(BaseModel):
    plus: List[str] = []
    minus: List[str] = []


class FundSignal(BaseModel):
    code: str
    score: int
    signal: str
    current_premium: Optional[float] = None
    current_volume: Optional[float] = None
    price_pct: Optional[float] = None
    key_metrics: KeyMetrics = KeyMetrics()
    reasons: Reasons = Reasons()
    purchase_info: PurchaseInfo = PurchaseInfo()
    data_as_of: Optional[str] = None
    is_estimated: bool = True


class FundDetail(FundSignal):
    history_summary: Optional[Dict[str, Any]] = None


class OpportunityListResponse(BaseModel):
    data: List[FundSignal]
    count: int
    filters: Dict[str, Any]


class DataStatusResponse(BaseModel):
    sync_time: Optional[str] = None
    overall_latest: Optional[str] = None
    overall_lag_days: Optional[int] = None
    total_lofs: int
    status: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class FundHistoryRecord(BaseModel):
    date: str
    price: Optional[float] = None
    net_value: Optional[float] = None
    est_val: Optional[float] = None
    discount_rt: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None


class FundHistoryResponse(BaseModel):
    code: str
    records: List[FundHistoryRecord]
    days: int
