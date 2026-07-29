"""
定时任务调度器
在 FastAPI 应用启动时自动注册，随容器生命周期运行
每日晚间净值公布后自动同步数据（含 LOF 清单更新），周末/节假日自动跳过
"""
import os
import sys
import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "scripts"))

# 全局调度器实例
scheduler: AsyncIOScheduler = None

# 同步时点（北京时间）：仅在晚间净值更新后执行一次同步
# 盘中不再同步，避免获取到缺失溢价率的半成品数据
SYNC_TIMES = [
    {"hour": 21, "minute": 0},    # 晚间：基金公司公布当日净值后
]


def _run_sync():
    """执行数据同步（在线程池中运行，不阻塞事件循环）"""
    now_str = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[scheduler] 定时同步触发 ({now_str})")

    try:
        from utils.trading_calendar import is_trading_day
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if not is_trading_day(today):
            logger.info(f"[scheduler] {today} 非交易日，跳过")
            return

        from core.data_sync import DataSyncCore
        from fetch_fund_purchase import fetch_or_load_fund_purchase
        from discover_new_lof import discover_and_update

        # 1. 更新 LOF 清单（发现新上市 / 清理退市，每天一次）
        try:
            logger.info("[scheduler] 检查 LOF 清单变动...")
            new_codes, delisted_codes = discover_and_update()
            if new_codes:
                logger.info(f"[scheduler] 发现 {len(new_codes)} 个新 LOF")
            if delisted_codes:
                logger.info(f"[scheduler] 清理 {len(delisted_codes)} 个退市 LOF")
        except Exception as e:
            logger.error(f"[scheduler] LOF 清单更新失败: {e}")

        # 2. 同步基金申购赎回信息
        try:
            logger.info("[scheduler] 同步基金申购赎回信息...")
            fetch_or_load_fund_purchase()
        except Exception as e:
            logger.error(f"[scheduler] 申购信息同步失败: {e}")

        # 3. 增量数据同步
        logger.info("[scheduler] 执行增量数据同步...")
        syncer = DataSyncCore()
        results = syncer.sync_all()

        updated = len(results['updated'])
        total = updated + len(results['no_change']) + len(results['failed'])
        new_records = sum(r['new'] for r in results['updated'])
        logger.info(f"[scheduler] 同步完成: {updated}/{total} 更新, {new_records} 条新增, {len(results['failed'])} 失败")

        # 4. 写入同步时间
        sync_time_path = os.path.join(project_root, "data", "last_sync_time.txt")
        now_cn = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
        with open(sync_time_path, "w", encoding="utf-8") as f:
            f.write(now_cn)

        # 5. 写入同步报告
        import json
        report_path = os.path.join(project_root, "data", "last_sync_report.json")
        report = {
            "sync_time": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "updated_count": updated,
            "no_change_count": len(results['no_change']),
            "failed_count": len(results['failed']),
            "failed_codes": [r['code'] for r in results.get('failed', [])],
            "success": len(results['failed']) == 0
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 6. 数据质量检查
        try:
            logger.info("[scheduler] 执行数据质量检查...")
            import subprocess
            subprocess.run(
                [sys.executable, os.path.join(project_root, "scripts", "data_quality_check.py")],
                check=False, capture_output=True, text=True, timeout=120
            )
        except Exception as e:
            logger.error(f"[scheduler] 数据质量检查失败: {e}")

        # 7. 清除 API 内存缓存，使下次请求加载新数据
        try:
            from core.analyzer import invalidate_analyzer_cache, get_analyzer
            invalidate_analyzer_cache()
            logger.info("[scheduler] API 缓存已清除，下次请求将加载新数据")

            # 8. 预计算套利信号并写入磁盘缓存（加速服务重启）
            analyzer = get_analyzer()
            analyzer.get_all_signals()  # 触发全量计算
            if analyzer.save_signals_cache():
                logger.info("[scheduler] 预计算信号缓存已写入 opportunities_cache.json")
            else:
                logger.warning("[scheduler] 预计算信号缓存写入失败")
        except Exception as e:
            logger.error(f"[scheduler] 缓存处理失败: {e}")

    except Exception as e:
        logger.error(f"[scheduler] 同步任务异常: {e}")
        logger.error(traceback.format_exc())


def init_scheduler():
    """初始化并启动定时调度器"""
    global scheduler

    if scheduler is not None:
        logger.warning("[scheduler] 调度器已存在，跳过初始化")
        return scheduler

    tz = ZoneInfo("Asia/Shanghai")
    scheduler = AsyncIOScheduler(timezone=tz)

    # 注册盘中同步任务
    for t in SYNC_TIMES:
        trigger = CronTrigger(
            hour=t["hour"],
            minute=t["minute"],
            timezone=tz
        )
        scheduler.add_job(
            _run_sync,
            trigger=trigger,
            id=f"sync_{t['hour']:02d}{t['minute']:02d}",
            name=f"数据同步 {t['hour']:02d}:{t['minute']:02d}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

    scheduler.start()
    logger.info(f"[scheduler] 定时同步已启动，共 {len(SYNC_TIMES)} 个时点")
    for t in SYNC_TIMES:
        logger.info(f"  - {t['hour']:02d}:{t['minute']:02d}")

    return scheduler


def shutdown_scheduler():
    """关闭调度器"""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("[scheduler] 定度器已关闭")


def get_scheduler_info():
    """获取调度器状态信息"""
    if scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })

    return {
        "running": scheduler.running,
        "jobs": sorted(jobs, key=lambda x: x["next_run"] or "")
    }
