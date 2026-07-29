"""
自动发现新上市 LOF 基金（带类型筛选）

数据源：
1. ak.fund_lof_spot_em() —— 东方财富 LOF 实时行情（主源）
2. ak.fund_etf_category_ths(symbol="LOF") —— 同花顺 LOF 基金列表（补充源）
3. ak.fund_name_em() —— 东方财富基金基本信息（用于获取基金类型）

工作流程：
1. 从数据源拉取当前全市场 LOF 代码清单
2. 通过 fund_name_em() 获取基金类型，剔除无套利价值的类型
3. 与 all_LOF.txt 做差集比对
4. 新代码追加到 all_LOF.txt 末尾
5. 已退市 LOF（在清单中但市场已无）从 all_LOF.txt 移除，并清理对应数据文件

筛选规则：
- 剔除债券型（净值波动小，无溢价套利空间）
- 剔除货币型/固收型/理财型
- 剔除 FOF-稳健型（底层多为债券，波动小）
- 保留股票型/指数型/混合型/QDII/FOF-进取型等
"""
import os
import sys
import logging
from typing import List, Tuple, Set, Dict, Optional

import akshare as ak
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

# ===== 筛选配置 =====
# 基金类型中包含以下关键词的将被剔除（无套利价值）
EXCLUDE_TYPE_KEYWORDS = [
    '债券', '货币', '固收', '理财', '中短债', '信用债', '长债',
]

# FOF 中仅保留进取型和均衡型，剔除稳健型
EXCLUDE_FOF_KEYWORDS = ['FOF-稳健']


def get_lof_file_path() -> str:
    """获取 all_LOF.txt 路径"""
    return os.path.join(project_root, 'all_LOF.txt')


def load_existing_codes() -> List[str]:
    """读取现有 all_LOF.txt 中的 LOF 代码"""
    lof_file = get_lof_file_path()
    with open(lof_file, 'r', encoding='utf-8') as f:
        codes = [line.strip() for line in f if line.strip()]
    logger.info(f"现有 LOF 清单: {len(codes)} 个代码")
    return codes


def fetch_lof_codes_from_eastmoney() -> Set[str]:
    """从东方财富获取全市场 LOF 代码（主源）"""
    try:
        df = ak.fund_lof_spot_em()
        codes = set(df['代码'].astype(str).str.zfill(6).tolist())
        logger.info(f"东方财富 LOF 实时行情: {len(codes)} 个代码")
        return codes
    except Exception as e:
        logger.warning(f"东方财富 LOF 行情获取失败: {e}")
        return set()


def fetch_lof_codes_from_ths() -> Set[str]:
    """从同花顺获取 LOF 基金代码（补充源）"""
    try:
        df = ak.fund_etf_category_ths(symbol="LOF")
        codes = set(df['基金代码'].astype(str).str.zfill(6).tolist())
        logger.info(f"同花顺 LOF 基金列表: {len(codes)} 个代码")
        return codes
    except Exception as e:
        logger.warning(f"同花顺 LOF 列表获取失败: {e}")
        return set()


def fetch_fund_type_map() -> Dict[str, str]:
    """获取全市场基金代码 → 基金类型的映射"""
    try:
        df = ak.fund_name_em()
        type_map = dict(zip(
            df['基金代码'].astype(str).str.zfill(6),
            df['基金类型'].astype(str)
        ))
        logger.info(f"获取基金类型映射: {len(type_map)} 条")
        return type_map
    except Exception as e:
        logger.warning(f"获取基金类型失败: {e}")
        return {}


def fetch_market_lof_codes() -> Set[str]:
    """合并多个数据源，获取全市场 LOF 代码"""
    codes = fetch_lof_codes_from_eastmoney()
    codes |= fetch_lof_codes_from_ths()

    if not codes:
        logger.error("所有数据源均获取失败，无法发现新 LOF")
        return set()

    logger.info(f"合并去重后全市场 LOF: {len(codes)} 个代码")
    return codes


def is_arbitrage_candidate(fund_type: str) -> bool:
    """
    判断基金类型是否有套利价值

    剔除：债券型、货币型、固收型、理财型、FOF-稳健型
    保留：股票型、指数型、混合型、QDII、FOF-进取/均衡型等
    """
    if not fund_type or fund_type == 'nan':
        # 类型未知，保守保留（宁可多拉数据也不漏）
        return True

    # 剔除债券/货币/固收/理财
    for kw in EXCLUDE_TYPE_KEYWORDS:
        if kw in fund_type:
            return False

    # 剔除 FOF-稳健型
    for kw in EXCLUDE_FOF_KEYWORDS:
        if kw in fund_type:
            return False

    return True


def filter_by_type(codes: Set[str], type_map: Dict[str, str]) -> Tuple[Set[str], List[Tuple[str, str]]]:
    """
    按基金类型筛选

    Returns:
        (kept_codes, excluded_list)
        kept_codes: 通过筛选的代码集合
        excluded_list: 被剔除的 (code, type) 列表
    """
    if not type_map:
        logger.warning("无类型映射，跳过类型筛选，全部保留")
        return codes, []

    kept = set()
    excluded = []

    for code in codes:
        fund_type = type_map.get(code, '')
        if is_arbitrage_candidate(fund_type):
            kept.add(code)
        else:
            excluded.append((code, fund_type))

    logger.info(f"类型筛选: 保留 {len(kept)}, 剔除 {len(excluded)}")
    return kept, excluded


def remove_delisted_codes(delisted_codes: List[str]):
    """从 all_LOF.txt 移除已退市的 LOF，并清理对应数据文件"""
    if not delisted_codes:
        return

    lof_file = get_lof_file_path()
    delisted_set = set(delisted_codes)

    # 1. 重写 all_LOF.txt，移除退市代码
    with open(lof_file, 'r', encoding='utf-8') as f:
        all_codes = [line.strip() for line in f if line.strip()]

    kept_codes = [c for c in all_codes if c not in delisted_set]
    with open(lof_file, 'w', encoding='utf-8') as f:
        for code in kept_codes:
            f.write(f"{code}\n")

    # 2. 清理对应的数据文件 data/lof_{code}.csv
    data_dir = os.path.join(project_root, 'data')
    removed_files = []
    for code in delisted_codes:
        csv_path = os.path.join(data_dir, f'lof_{code}.csv')
        if os.path.exists(csv_path):
            os.remove(csv_path)
            removed_files.append(csv_path)

    logger.info(
        f"🗑 已移除 {len(delisted_codes)} 个退市 LOF，"
        f"清单 {len(all_codes)} → {len(kept_codes)}，"
        f"清理 {len(removed_files)} 个数据文件"
    )


def discover_and_update() -> Tuple[List[str], List[str]]:
    """
    发现新 LOF 并更新清单文件

    Returns:
        (new_codes, delisted_codes)
        new_codes: 新发现的 LOF 代码列表
        delisted_codes: 疑似退市的 LOF 代码列表（在清单中但市场已无）
    """
    existing_codes = load_existing_codes()
    existing_set = set(existing_codes)

    market_codes = fetch_market_lof_codes()
    if not market_codes:
        return [], []

    # 获取基金类型并筛选
    type_map = fetch_fund_type_map()
    market_codes_filtered, excluded_by_type = filter_by_type(market_codes, type_map)

    if excluded_by_type:
        excluded_summary = {}
        for code, t in excluded_by_type:
            excluded_summary.setdefault(t, []).append(code)
        for t, codes_list in excluded_summary.items():
            logger.info(f"  剔除类型 [{t}]: {len(codes_list)} 个")

    # 差集：市场有但清单没有 → 新 LOF
    new_codes = sorted(market_codes_filtered - existing_set)
    # 差集：清单有但市场没有 → 疑似退市
    delisted_codes = sorted(existing_set - market_codes)

    # 追加新代码到 all_LOF.txt
    if new_codes:
        lof_file = get_lof_file_path()
        with open(lof_file, 'a', encoding='utf-8') as f:
            for code in new_codes:
                f.write(f"{code}\n")
        logger.info(f"✅ 发现 {len(new_codes)} 个新 LOF（已通过类型筛选），已追加到 all_LOF.txt")
        for code in new_codes:
            t = type_map.get(code, '未知')
            logger.info(f"  + {code}  {t}")
    else:
        logger.info("未发现新 LOF，清单已是最新")

    if delisted_codes:
        logger.warning(
            f"⚠️  检测到 {len(delisted_codes)} 个 LOF 已退市: {', '.join(delisted_codes)}"
        )
        remove_delisted_codes(delisted_codes)

    return new_codes, delisted_codes


if __name__ == "__main__":
    new_codes, delisted_codes = discover_and_update()
    print(f"\n{'='*50}")
    print(f"新发现 LOF: {len(new_codes)} 个")
    if new_codes:
        for code in new_codes:
            print(f"  + {code}")
    print(f"疑似退市 LOF: {len(delisted_codes)} 个")
    if delisted_codes:
        for code in delisted_codes:
            print(f"  - {code}")
    print(f"{'='*50}")
