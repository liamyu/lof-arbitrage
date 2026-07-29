"""
数据质量检查脚本
检查 LOF 数据的新鲜度、完整性、异常值
输出检查报告，供 API 和后续流程使用
"""
import sys
import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Any

import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.data_manager import DataManager
from utils.trading_calendar import is_trading_day

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DataQualityChecker:
    """数据质量检查器"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = os.path.join(project_root, data_dir)
        self.manager = DataManager(data_dir)
        self.issues: List[Dict[str, Any]] = []
        self.stats: Dict[str, Any] = {}

    def _load_all_data(self) -> Dict[str, pd.DataFrame]:
        """加载所有 LOF 数据"""
        files = [f for f in os.listdir(self.data_dir)
                 if f.startswith('lof_') and f.endswith('.csv')]
        data = {}
        for file in files:
            code = file.replace('lof_', '').replace('.csv', '')
            try:
                df = pd.read_csv(os.path.join(self.data_dir, file))
                df['price_dt'] = pd.to_datetime(df['price_dt'])
                data[code] = df
            except Exception as e:
                self.issues.append({
                    'code': code,
                    'severity': 'error',
                    'category': 'load_failed',
                    'message': f'加载失败: {e}'
                })
        return data

    def check_freshness(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """检查数据新鲜度"""
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        latest_dates = []
        stale_count = 0
        very_stale_count = 0

        for code, df in data.items():
            latest = df['price_dt'].max().date()
            latest_dates.append(latest)
            days_behind = (today - latest).days

            if days_behind > 7:
                very_stale_count += 1
                self.issues.append({
                    'code': code,
                    'severity': 'error',
                    'category': 'very_stale',
                    'message': f'数据严重过期: 最新 {latest}, 滞后 {days_behind} 天'
                })
            elif days_behind > 2:
                stale_count += 1
                self.issues.append({
                    'code': code,
                    'severity': 'warning',
                    'category': 'stale',
                    'message': f'数据过期: 最新 {latest}, 滞后 {days_behind} 天'
                })

        if latest_dates:
            overall_latest = max(latest_dates)
            overall_lag = (today - overall_latest).days
        else:
            overall_latest = None
            overall_lag = None

        return {
            'overall_latest': str(overall_latest) if overall_latest else None,
            'overall_lag_days': overall_lag,
            'stale_count': stale_count,
            'very_stale_count': very_stale_count,
            'total_checked': len(data)
        }

    def check_completeness(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """检查数据完整性"""
        missing_discount = 0
        missing_price = 0
        low_record_count = 0

        for code, df in data.items():
            # 检查关键字段缺失
            if 'discount_rt' in df.columns:
                na_count = df['discount_rt'].isna().sum()
                if na_count > 0:
                    missing_discount += 1
                    if na_count > len(df) * 0.2:  # 超过 20% 缺失
                        self.issues.append({
                            'code': code,
                            'severity': 'warning',
                            'category': 'missing_discount',
                            'message': f'溢价率缺失 {na_count}/{len(df)} 条'
                        })

            if 'price' in df.columns:
                na_count = df['price'].isna().sum()
                if na_count > 0:
                    missing_price += 1

            # 检查记录数过少
            if len(df) < 10:
                low_record_count += 1
                self.issues.append({
                    'code': code,
                    'severity': 'warning',
                    'category': 'low_records',
                    'message': f'记录数过少: {len(df)} 条'
                })

        return {
            'missing_discount': missing_discount,
            'missing_price': missing_price,
            'low_record_count': low_record_count,
            'total_checked': len(data)
        }

    def check_anomalies(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """检查异常值"""
        extreme_premium = 0  # 溢价率极端值 (>50% 或 <-30%)
        negative_price = 0

        for code, df in data.items():
            if 'discount_rt' in df.columns:
                recent = df.tail(5)['discount_rt'].dropna()
                if not recent.empty:
                    max_premium = recent.max()
                    min_premium = recent.min()
                    if max_premium > 50 or min_premium < -30:
                        extreme_premium += 1
                        self.issues.append({
                            'code': code,
                            'severity': 'warning',
                            'category': 'extreme_premium',
                            'message': f'近期溢价率极端: 最高 {max_premium:.2f}%, 最低 {min_premium:.2f}%'
                        })

            if 'price' in df.columns:
                if (df['price'] <= 0).any():
                    negative_price += 1
                    self.issues.append({
                        'code': code,
                        'severity': 'error',
                        'category': 'invalid_price',
                        'message': '存在非正价格'
                    })

        return {
            'extreme_premium': extreme_premium,
            'negative_price': negative_price,
            'total_checked': len(data)
        }

    def run_all_checks(self) -> Dict[str, Any]:
        """运行全部检查"""
        logger.info("开始数据质量检查...")
        data = self._load_all_data()

        if not data:
            logger.error("未加载到任何数据")
            return {
                'status': 'failed',
                'reason': 'no_data',
                'issues': [],
                'stats': {}
            }

        logger.info(f"已加载 {len(data)} 个 LOF 数据文件")

        freshness = self.check_freshness(data)
        completeness = self.check_completeness(data)
        anomalies = self.check_anomalies(data)

        # 汇总统计
        self.stats = {
            'freshness': freshness,
            'completeness': completeness,
            'anomalies': anomalies,
            'total_lofs': len(data),
            'total_issues': len(self.issues),
            'error_count': sum(1 for i in self.issues if i['severity'] == 'error'),
            'warning_count': sum(1 for i in self.issues if i['severity'] == 'warning')
        }

        # 判断整体状态
        if self.stats['error_count'] > 20:
            status = 'failed'
        elif self.stats['error_count'] > 0 or self.stats['warning_count'] > 50:
            status = 'degraded'
        else:
            status = 'healthy'

        self.stats['status'] = status

        logger.info(f"检查完成: 状态={status}, 错误={self.stats['error_count']}, 警告={self.stats['warning_count']}")

        return {
            'status': status,
            'check_time': datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            'stats': self.stats,
            'issues': self.issues[:50]  # 只保留前 50 条
        }

    def write_report(self, report: Dict[str, Any]):
        """写入检查报告"""
        report_path = os.path.join(project_root, "data", "data_quality_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"质量报告已写入: {report_path}")


def main():
    checker = DataQualityChecker()
    report = checker.run_all_checks()
    checker.write_report(report)

    if report['status'] == 'failed':
        logger.error("❌ 数据质量检查未通过")
        sys.exit(1)
    elif report['status'] == 'degraded':
        logger.warning("⚠️ 数据质量降级，存在部分问题")
        # 降级不退出失败，但会记录
    else:
        logger.info("✅ 数据质量检查通过")


if __name__ == "__main__":
    main()
