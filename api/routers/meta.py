"""
元数据路由
GET /api/v1/health
GET /api/v1/meta/data-status
"""
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from api.models import HealthResponse, DataStatusResponse
from core.analyzer import get_project_root

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/health")
def health() -> HealthResponse:
    """服务健康检查"""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    )


@router.get("/data-status")
def data_status() -> DataStatusResponse:
    """
    获取数据同步状态
    """
    project_root = get_project_root()

    # 读取最后同步时间
    sync_time = None
    sync_path = os.path.join(project_root, "data", "last_sync_time.txt")
    if os.path.exists(sync_path):
        with open(sync_path, "r", encoding="utf-8") as f:
            sync_time = f.read().strip()

    # 读取数据质量报告
    overall_latest = None
    overall_lag_days = None
    status = "unknown"
    report_path = os.path.join(project_root, "data", "data_quality_report.json")
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            freshness = report.get("stats", {}).get("freshness", {})
            overall_latest = freshness.get("overall_latest")
            overall_lag_days = freshness.get("overall_lag_days")
            status = report.get("status", "unknown")
        except Exception:
            pass

    # 统计 LOF 数量
    data_dir = os.path.join(project_root, "data")
    total_lofs = 0
    if os.path.exists(data_dir):
        total_lofs = len([f for f in os.listdir(data_dir)
                         if f.startswith('lof_') and f.endswith('.csv')])

    return DataStatusResponse(
        sync_time=sync_time,
        overall_latest=overall_latest,
        overall_lag_days=overall_lag_days,
        total_lofs=total_lofs,
        status=status
    )
