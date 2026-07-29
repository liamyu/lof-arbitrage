"""
清理过期数据，控制磁盘占用

清理对象：
1. data/lof_{code}.csv — 每个 LOF 的历史行情，只保留最近 N 天
2. data/fund_purchase_em_*.csv — 申购信息缓存，只保留最近 1 天（fetch_fund_purchase.py 已自动清理非当天文件，这里做兜底）

保留天数默认 35 天（评分引擎需要 30 天历史 + 5 天缓冲）。
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 保留天数（评分引擎需要 30 天历史 + 缓冲）
DEFAULT_KEEP_DAYS = 35


def cleanup_lof_csv(keep_days: int = DEFAULT_KEEP_DAYS) -> int:
    """
    裁剪每个 LOF CSV 文件，只保留最近 keep_days 天的数据

    Returns:
        清理的文件数
    """
    data_dir = os.path.join(project_root, 'data')
    if not os.path.exists(data_dir):
        return 0

    cutoff_date = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=keep_days)
    cleaned_count = 0
    total_removed_rows = 0

    for fname in os.listdir(data_dir):
        if not (fname.startswith('lof_') and fname.endswith('.csv')):
            continue

        filepath = os.path.join(data_dir, fname)
        try:
            df = pd.read_csv(filepath, dtype=str)
            if 'price_dt' not in df.columns or df.empty:
                continue

            df['price_dt'] = pd.to_datetime(df['price_dt'], errors='coerce')
            original_len = len(df)

            # 只保留 cutoff 之后的记录
            df = df[df['price_dt'].dt.date >= cutoff_date]

            if len(df) < original_len:
                removed = original_len - len(df)
                total_removed_rows += removed

                if df.empty:
                    # 裁剪后为空，说明这个 LOF 数据全部过期，保留文件但跳过写入
                    logger.warning(f"{fname}: 全部 {original_len} 条记录已过期，跳过（保留空文件）")
                    continue

                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                cleaned_count += 1
        except Exception as e:
            logger.error(f"清理 {fname} 失败: {e}")

    if cleaned_count > 0:
        logger.info(f"CSV 裁剪完成: {cleaned_count} 个文件, 移除 {total_removed_rows} 条过期记录 (保留 {keep_days} 天)")
    else:
        logger.info(f"CSV 无需裁剪 (保留 {keep_days} 天)")

    return cleaned_count


def cleanup_purchase_cache() -> int:
    """
    清理过期的申购信息缓存文件，只保留最新一份

    Returns:
        清理的文件数
    """
    data_dir = os.path.join(project_root, 'data')
    if not os.path.exists(data_dir):
        return 0

    purchase_files = []
    for fname in os.listdir(data_dir):
        if fname.startswith('fund_purchase_em_') and fname.endswith('.csv'):
            purchase_files.append(fname)

    if len(purchase_files) <= 1:
        return 0

    # 按文件名中的日期排序，保留最新的
    purchase_files.sort(reverse=True)
    removed = 0
    for fname in purchase_files[1:]:
        os.remove(os.path.join(data_dir, fname))
        removed += 1
        logger.info(f"删除过期申购缓存: {fname}")

    if removed > 0:
        logger.info(f"申购缓存清理: 移除 {removed} 个旧文件")

    return removed


def cleanup(keep_days: int = DEFAULT_KEEP_DAYS) -> dict:
    """
    执行完整清理

    Returns:
        {"lof_csv_cleaned": int, "purchase_cache_removed": int}
    """
    logger.info(f"🧹 开始清理过期数据 (保留 {keep_days} 天)...")
    lof_cleaned = cleanup_lof_csv(keep_days)
    purchase_removed = cleanup_purchase_cache()
    logger.info(f"🧹 清理完成")
    return {"lof_csv_cleaned": lof_cleaned, "purchase_cache_removed": purchase_removed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="清理过期 LOF 数据")
    parser.add_argument("--days", type=int, default=DEFAULT_KEEP_DAYS, help=f"保留天数 (默认 {DEFAULT_KEEP_DAYS})")
    args = parser.parse_args()

    result = cleanup(args.days)
    print(f"\n{'='*50}")
    print(f"LOF CSV 裁剪: {result['lof_csv_cleaned']} 个文件")
    print(f"申购缓存清理: {result['purchase_cache_removed']} 个文件")
    print(f"{'='*50}")
