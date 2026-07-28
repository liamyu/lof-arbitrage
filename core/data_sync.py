"""
智能增量数据同步核心模块
处理集思录API滚动窗口50条限制的数据同步
新增：重试机制、限流、数据校验、详细日志
"""
import requests
import pandas as pd
import os
import json
import time
import shutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DataSyncCore:
    """核心数据同步器（增强版）"""

    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0, request_interval: float = 0.5):
        current_file = os.path.abspath(__file__)
        core_dir = os.path.dirname(current_file)
        project_root = os.path.dirname(core_dir)

        self.data_dir = os.path.join(project_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_interval = request_interval

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.jisilu.cn/',
        }
        self.params = {
            '___jsl': 'LST___t',
            'rp': '50',
            'page': '1'
        }

        self._last_request_time: Optional[float] = None

    def _rate_limit(self):
        """请求限流"""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.request_interval:
                sleep_time = self.request_interval - elapsed
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request_with_retry(self, url: str, params: dict, headers: dict) -> Optional[dict]:
        """带重试的 HTTP GET 请求"""
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30,
                    allow_redirects=False
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                        return data
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析失败 (attempt {attempt}): {e}")
                        return None
                elif response.status_code in (429, 503, 502, 504):
                    # 限流或服务不可用，等待后重试
                    wait = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"HTTP {response.status_code}，{wait}s 后重试 (attempt {attempt}/{self.max_retries})")
                    time.sleep(wait)
                else:
                    logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常 (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)

        logger.error(f"请求失败，已达最大重试次数 ({self.max_retries})")
        return None

    def load_lof_codes(self) -> List[str]:
        """读取LOF代码列表"""
        try:
            current_script_path = os.path.abspath(__file__)
            current_script_dir = os.path.dirname(current_script_path)
            parent_dir = os.path.dirname(current_script_dir)
            lof_file_path = os.path.join(parent_dir, 'all_LOF.txt')

            with open(lof_file_path, 'r', encoding='utf-8') as f:
                codes = [line.strip() for line in f if line.strip()]
                logger.info(f"读取到 {len(codes)} 个 LOF 代码")
                return codes
        except FileNotFoundError:
            logger.error("all_LOF.txt 未找到")
            raise FileNotFoundError("all_LOF.txt not found")

    def load_existing_data(self, code: str) -> pd.DataFrame:
        """加载现有数据"""
        filename = f"{self.data_dir}/lof_{code}.csv"
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename, dtype=str)
                df['price_dt'] = pd.to_datetime(df['price_dt'])
                numeric_cols = ['price', 'discount_rt', 'net_value']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
            except Exception as e:
                logger.error(f"加载 {code} 失败: {e}")
        return pd.DataFrame()

    def _validate_api_response(self, data: dict, code: str) -> bool:
        """校验 API 响应数据格式"""
        if not isinstance(data, dict):
            logger.warning(f"[{code}] API 响应不是字典类型")
            return False
        if 'rows' not in data:
            logger.warning(f"[{code}] API 响应缺少 'rows' 字段")
            return False
        return True

    def _validate_record(self, record: dict, code: str) -> bool:
        """校验单条记录的关键字段"""
        required_fields = ['price_dt', 'price']
        for field in required_fields:
            if field not in record or pd.isna(record.get(field)):
                logger.debug(f"[{code}] 记录缺少关键字段: {field}")
                return False
        return True

    def fetch_api_data(self, code: str) -> pd.DataFrame:
        """获取API数据（增强版，带重试和校验）"""
        url = f"https://www.jisilu.cn/data/lof/hist_list/{code}"

        data = self._request_with_retry(url, self.params, self.headers)

        if data is None:
            return pd.DataFrame()

        if not self._validate_api_response(data, code):
            return pd.DataFrame()

        rows = data.get('rows', [])

        if not rows:
            logger.info(f"[{code}] API 返回空数据")
            return pd.DataFrame()

        records = []
        for row in rows:
            cell = row.get('cell', {})
            if not cell:
                continue
            record = dict(cell)
            record['code'] = code

            if self._validate_record(record, code):
                records.append(record)

        if not records:
            logger.warning(f"[{code}] 所有记录校验失败")
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # 数据类型转换
        df['price_dt'] = pd.to_datetime(df['price_dt'], errors='coerce')
        numeric_cols = ['price', 'discount_rt', 'net_value']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 丢弃日期解析失败的记录
        before_drop = len(df)
        df = df.dropna(subset=['price_dt'])
        after_drop = len(df)
        if after_drop < before_drop:
            logger.warning(f"[{code}] 丢弃 {before_drop - after_drop} 条日期解析失败的记录")

        logger.info(f"[{code}] 成功获取 {len(df)} 条记录")
        return df

    def sync_single_lof(self, code: str) -> Dict[str, Any]:
        """同步单个LOF，包括更新之前为"-"的溢价率数据"""
        existing_df = self.load_existing_data(code)
        api_df = self.fetch_api_data(code)

        if api_df.empty:
            return {
                'code': code,
                'status': 'failed',
                'existing': len(existing_df),
                'new': 0,
                'updated': 0,
                'total': len(existing_df),
                'error': 'API 返回空数据或请求失败'
            }

        if existing_df.empty:
            # 全新数据
            combined_df = api_df
            new_records = len(api_df)
            updated_records = 0
        else:
            # 智能合并：新增记录 + 更新已有记录
            api_df['price_dt_str'] = api_df['price_dt'].dt.strftime('%Y-%m-%d')
            existing_df['price_dt_str'] = existing_df['price_dt'].dt.strftime('%Y-%m-%d')

            merged_df = existing_df.copy()
            updated_records = 0

            for _, api_row in api_df.iterrows():
                api_date = api_row['price_dt_str']
                mask = merged_df['price_dt_str'] == api_date

                if mask.any():
                    # 已存在记录，检查是否需要更新
                    existing_discount = merged_df.loc[mask, 'discount_rt'].iloc[0]
                    if pd.isna(existing_discount) or str(existing_discount) == "-" or abs(existing_discount) < 0.01:
                        for col in api_row.index:
                            if col != 'price_dt_str':
                                merged_df.loc[mask, col] = api_row[col]
                        updated_records += 1
                else:
                    # 新增记录
                    new_row = api_row.to_dict()
                    new_row.pop('price_dt_str', None)
                    merged_df = pd.concat([merged_df, pd.DataFrame([new_row])], ignore_index=True)

            combined_df = merged_df.drop(columns=['price_dt_str'], errors='ignore')
            new_records = len(combined_df) - len(existing_df)

        if new_records > 0 or updated_records > 0:
            combined_df = combined_df.sort_values('price_dt').reset_index(drop=True)

            filename = f"{self.data_dir}/lof_{code}.csv"
            combined_df.to_csv(filename, index=False, encoding='utf-8-sig')

            return {
                'code': code,
                'status': 'updated',
                'existing': len(existing_df),
                'new': new_records,
                'updated': updated_records,
                'total': len(combined_df),
                'latest': combined_df['price_dt'].max().strftime('%Y-%m-%d')
            }

        return {
            'code': code,
            'status': 'no_change',
            'existing': len(existing_df),
            'new': 0,
            'updated': 0,
            'total': len(existing_df)
        }

    def sync_all(self) -> Dict[str, List[Dict]]:
        """同步所有LOF"""
        codes = self.load_lof_codes()
        results = {'updated': [], 'no_change': [], 'failed': []}

        total = len(codes)
        for idx, code in enumerate(codes, 1):
            try:
                logger.info(f"[{idx}/{total}] 正在同步 {code} ...")
                result = self.sync_single_lof(code)
                if result['status'] == 'updated':
                    results['updated'].append(result)
                    logger.info(f"[{code}] 更新: +{result['new']} 新, {result['updated']} 更新, 共 {result['total']} 条")
                elif result['status'] == 'no_change':
                    results['no_change'].append(result)
                else:
                    results['failed'].append(result)
                    logger.error(f"[{code}] 同步失败: {result.get('error', '未知错误')}")
            except Exception as e:
                logger.error(f"[{code}] 异常: {e}")
                results['failed'].append({'code': code, 'error': str(e)})

        # 汇总日志
        logger.info("=" * 50)
        logger.info(f"同步完成: 更新 {len(results['updated'])}, 无变化 {len(results['no_change'])}, 失败 {len(results['failed'])}")
        if results['failed']:
            failed_codes = [r['code'] for r in results['failed']]
            logger.warning(f"失败代码: {', '.join(failed_codes[:10])}{'...' if len(failed_codes) > 10 else ''}")

        return results
