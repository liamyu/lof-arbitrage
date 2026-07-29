"""
每日数据同步脚本
核心功能的简洁调用接口
增强版：修复导入路径、添加详细日志、失败统计、JSON 报告
"""
import sys
import os
import argparse
import json
import logging

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "scripts"))

from datetime import datetime
from zoneinfo import ZoneInfo
from utils.trading_calendar import is_trading_day
from core.data_sync import DataSyncCore
from utils.data_manager import DataManager
from fetch_fund_purchase import fetch_or_load_fund_purchase
from discover_new_lof import discover_and_update

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def write_last_update_time():
    """在 data 目录写入最近一次成功同步时间（北京时间）"""
    path = os.path.join(project_root, "data", "last_sync_time.txt")
    now_cn = datetime.now(ZoneInfo("Asia/Shanghai"))
    now_str = now_cn.strftime("%Y-%m-%d %H:%M")

    with open(path, "w", encoding="utf-8") as f:
        f.write(now_str)
    logger.info(f"已记录最后同步时间: {now_str}")


def write_sync_report(results: dict, duration_sec: float):
    """写入同步报告 JSON，供后续检查和通知使用"""
    report_path = os.path.join(project_root, "data", "last_sync_report.json")
    report = {
        "sync_time": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "duration_sec": round(duration_sec, 2),
        "updated_count": len(results.get('updated', [])),
        "no_change_count": len(results.get('no_change', [])),
        "failed_count": len(results.get('failed', [])),
        "failed_codes": [r['code'] for r in results.get('failed', [])],
        "success": len(results.get('failed', [])) == 0
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"同步报告已写入: {report_path}")


def main():
    start_time = datetime.now(ZoneInfo("Asia/Shanghai"))

    # ===== 交易日判断 =====
    today = start_time.date()
    if not is_trading_day(today):
        logger.info(f"📅 {today} 非交易日，跳过同步")
        return

    logger.info(f"📈 {today} 是交易日，开始同步数据...")

    # ===== 发现新上市 LOF & 清理退市 LOF =====
    try:
        logger.info("🔍 正在检查 LOF 清单变动...")
        new_codes, delisted_codes = discover_and_update()
        if new_codes:
            logger.info(f"🆕 发现 {len(new_codes)} 个新 LOF，将在本次同步中拉取数据")
        if delisted_codes:
            logger.info(f"🗑 已清理 {len(delisted_codes)} 个退市 LOF")
    except Exception as e:
        logger.error(f"LOF 清单更新失败（不阻断主流程）: {e}")

    # ===== 同步基金申购赎回信息 =====
    try:
        logger.info("正在同步基金申购赎回信息...")
        fetch_or_load_fund_purchase()
        logger.info("基金申购赎回信息同步完成")
    except Exception as e:
        logger.error(f"基金申购赎回信息同步失败: {e}")
        # 申购信息失败不阻断主流程

    parser = argparse.ArgumentParser(description="LOF每日数据同步")
    parser.add_argument("--init", action="store_true", help="首次初始化数据")
    parser.add_argument("--code", type=str, help="指定单个LOF代码")
    parser.add_argument("--verify", action="store_true", help="验证数据完整性")

    args = parser.parse_args()

    syncer = DataSyncCore()
    manager = DataManager()

    if args.init:
        logger.info("🚀 首次数据初始化...")
        results = syncer.sync_all()
        updated = len(results['updated'])
        total = len(results['updated']) + len(results['no_change']) + len(results['failed'])
        logger.info(f"✅ 初始化完成: {updated}/{total} 个LOF已更新")
        return

    if args.code:
        logger.info(f"🔄 同步单个LOF: {args.code}")
        result = syncer.sync_single_lof(args.code)
        logger.info(f"{result['code']}: {result['status']} - {result['existing']}→{result['total']}条")
        return

    if args.verify:
        logger.info("🔍 验证数据完整性...")
        summary = manager.get_data_summary()
        logger.info(f"📊 总LOF: {summary['total_lofs']}, 总记录: {summary['total_records']}")
        latest = list(summary['latest_dates'].items())[-5:]
        for code, date in latest:
            logger.info(f"  {code}: {date}")
        return

    # 默认：执行增量同步
    logger.info("🔄 执行增量数据同步...")
    results = syncer.sync_all()

    updated = len(results['updated'])
    total = len(results['updated']) + len(results['no_change']) + len(results['failed'])
    new_records = sum(r['new'] for r in results['updated'])

    logger.info(f"✅ 同步完成: {updated}/{total} 个LOF更新, 新增{new_records}条记录")

    # 写入最后同步时间和报告
    write_last_update_time()
    duration = (datetime.now(ZoneInfo("Asia/Shanghai")) - start_time).total_seconds()
    write_sync_report(results, duration)

    # 如果有失败，以非零退出码退出
    if results['failed']:
        failed_pct = len(results['failed']) / total * 100
        logger.warning(f"失败比例: {failed_pct:.1f}%")
        if failed_pct > 20:
            logger.error("失败比例超过 20%，视为异常")
            sys.exit(1)


if __name__ == "__main__":
    main()
