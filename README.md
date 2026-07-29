# LOF 溢价套利监测系统

> **给 AI 助手的上下文说明**：本 README 是项目唯一权威结构文档。修改代码前请通读"核心模块"和"开发约定"两节。

## 项目简介

LOF（上市开放式基金）溢价/折价套利监测系统。从集思录抓取全市场 LOF 的溢价率行情，从东方财富（akshare）抓取基金申购赎回信息和基金类型，经评分引擎计算套利机会得分和净利润预估，通过 FastAPI REST API 和 Vue 3 移动端 H5 页面对外展示。数据同步由容器内 APScheduler 定时任务在交易日晚间自动执行（净值公布后），并自动发现新上市 LOF、清理退市 LOF、自动清理过期数据。

- **数据源**：集思录 `jisilu.cn`（LOF 溢价率历史行情）、东方财富 `akshare`（基金申购赎回状态、基金类型、LOF 清单）
- **后端**：FastAPI + Pandas + NumPy + APScheduler
- **前端**：Vue 3（单文件 SPA `h5/index.html`，使用本地 vendor，生产部署直接用）
- **部署**：Docker Compose（FastAPI + Nginx），目标平台：极空间 NAS / 任意 Docker 环境
- **定时任务**：容器内 APScheduler（交易日 21:00 同步，不再使用 GitHub Actions）
- **数据保留**：自动清理过期数据，保留最近 64 天（匹配前端历史图表 60 天默认展示）
- **时区**：全链路使用 `Asia/Shanghai`

## 目录结构

```
lof-arbitrage/
├── api/                        # FastAPI 后端
│   ├── main.py                 # 应用入口，lifespan 启动 scheduler，注册路由 + CORS
│   ├── models.py               # Pydantic 响应模型（含 CostBreakdown、净利润字段）
│   └── routers/
│       ├── opportunities.py    # GET /api/v1/opportunities（机会列表）
│       ├── funds.py            # GET /api/v1/funds/{code}（详情/评分/历史）
│       └── meta.py             # GET /api/v1/meta/data-status（数据状态）
├── core/                       # 核心业务逻辑
│   ├── analyzer.py             # 评分引擎 LOFArbitrageAnalyzer（含净利润、折价套利、QDII、T+2风险）
│   ├── data_sync.py            # 数据同步器 DataSyncCore（集思录 API + 增量合并）
│   └── scheduler.py            # APScheduler 定时任务调度器（容器内自运行）
├── utils/                      # 工具模块
│   ├── data_manager.py         # DataManager 数据读写验证
│   └── trading_calendar.py     # 交易日判断（上交所 SSE 日历，pandas_market_calendars）
├── scripts/                    # 运维脚本
│   ├── sync_daily.py           # 每日数据同步入口（CLI 手动触发用）
│   ├── data_quality_check.py   # 数据质量检查（新鲜度/完整性/异常值）
│   ├── fetch_fund_purchase.py  # 抓取基金申购信息（akshare + 当日缓存）
│   ├── discover_new_lof.py     # 自动发现新上市LOF + 类型筛选 + 清理退市
│   └── cleanup_old_data.py     # 过期数据清理（保留64天）
├── h5/                         # 前端
│   ├── index.html              # 单文件 Vue 3 SPA（793 行，本地 vendor，生产部署用）
│   ├── vendor/                 # vue.global.js + vue-router.global.js（本地，不依赖 CDN）
│   ├── src/                    # Vite + Vue 3 SFC 版（开发用，功能较简化）
│   │   ├── views/{Opportunities,FundDetail,DataStatus}.vue
│   │   ├── api.js / router.js / main.js / App.vue
│   ├── package.json / vite.config.js
│   └── dist/                   # 构建产物（vite build 输出）
├── data/                       # ⚠️ 运行时数据目录（已 gitignore，容器卷挂载）
│   ├── lof_*.csv               # LOF 历史行情 CSV
│   ├── fund_purchase_em_*.csv  # 当日申购信息缓存
│   ├── last_sync_time.txt      # 最后同步时间
│   ├── last_sync_report.json   # 同步报告
│   └── data_quality_report.json# 质量检查报告
├── all_LOF.txt                 # LOF 代码清单（动态更新，discover_new_lof.py 维护）
├── Dockerfile                  # API 服务镜像（python:3.11-slim）
├── docker-compose.yml          # 极空间 Docker Compose 配置（api + nginx）
├── deploy.sh                   # 一键部署脚本
├── DEPLOY_ZSPACE.md            # 极空间部署指南
├── requirements.txt
├── .gitignore
└── README.md                   # 本文件
```

## 核心模块

### 1. 评分引擎 `core/analyzer.py`

`LOFArbitrageAnalyzer` 是纯数据服务类，无 Streamlit/UI 依赖。

**评分维度（总分 100）**：
- **溢价/折价率维度**（权重 60%，最高 60 分）：当前溢/折价率绝对值、相对 5/10/15 日均值的偏离、近 3 日趋势、极端区间加成、价格涨跌幅惩罚
- **流动性维度**（权重 50%，最高 40 分）：近 3 日成交额/份额是否达 1000 万阈值、份额增速稳定性、套利盘撤离信号

**套利方向**（`arbitrage_direction`）：
- `premium`（溢价套利）：申购 + 场内卖出，成本 = 申购费 + 交易佣金
- `discount`（折价套利）：场内买入 + 赎回，成本 = 赎回费 + 交易佣金

**新增功能（v2 升级）**：
- **净利润计算**（`calculate_premium_net_profit` / `calculate_discount_net_profit`）：扣除申购/赎回费和交易佣金后的真实套利空间
- **成本明细**（`cost_breakdown`）：gross_spread、purchase_fee、redeem_fee、trade_commission、total_cost
- **净利润等级**（`net_profit_to_signal`）：利润充足(≥3%) / 利润微薄(≥1%) / 薄利边缘(>0) / 基本无利(>-1%) / 亏损风险
- **折价套利评分**：折价率绝对值为基础，价格涨停惩罚（折价可能快速收敛）
- **QDII 识别与扣分**（`is_qdii_fund`）：QDII 到账周期更长(T+3+)，评分扣减 10 分
- **T+2 风险量化**（`calculate_t2_risk`）：历史最大 2 日不利变动，若净利润不足以覆盖则额外扣分
- **交易佣金参数**（`trade_commission`，默认 0.020% 即万 2）
- **T-1 数据回退**：当日溢价率缺失时自动回退到最近有效记录，并标记 `is_t1_fallback`
- **最低净利润过滤**（`min_net_profit`）：API 可按净利润阈值筛选

**评分等级**（`score_to_signal`）：≥80 评分优秀 / ≥65 评分良好 / ≥50 评分中等 / ≥35 评分一般 / <35 不推荐

**硬性过滤**（`get_purchase_block_reason`）：申购暂停/封闭期/认购期、限额为 0、限额过低（默认 <1000 元）、手续费过高（默认 >0.5%）

**关键方法**：
- `load_all_data()` — 加载 `data/lof_*.csv`，用估值 `est_val` 回填缺失的 `discount_rt`
- `load_purchase_info()` — 加载 `data/fund_purchase_em_*.csv` 申购信息（含 fund_type）
- `score_one_lof(lof_data, code, purchase_info, trade_commission)` — 单只 LOF 评分
- `get_all_signals(trade_commission)` — 全市场评分，按分数降序
- `get_opportunities(min_score, purchase_open, max_fee, min_purchase_limit, trade_commission, min_net_profit)` — 过滤后的机会列表
- `get_fund_detail(code, trade_commission)` — 单只详情（含历史摘要）

**辅助函数**：
- `parse_purchase_limit()` — 解析"限购100万"/"无限制"等字符串
- `is_purchase_open()` — 判断是否可申购
- `estimate_redeem_fee()` — 估计赎回费率（按持有期分档）
- `is_qdii_fund()` — QDII 基金识别

### 2. 数据同步 `core/data_sync.py`

`DataSyncCore` 处理集思录 API 的 50 条滚动窗口限制：
- 请求限流（`request_interval` 默认 0.5s）
- 带指数退避的重试（`max_retries` 默认 3）
- 增量合并：新增记录 + 更新已有记录中溢价率为空/"-"的行
- 响应与记录级别的数据校验
- 数据保留：自动清理超过 64 天的过期数据（匹配前端 60 天图表默认值）

### 3. 定时调度器 `core/scheduler.py`

`APScheduler` + `AsyncIOScheduler`，随 FastAPI 应用生命周期启动/关闭。

**调度配置**：
- 仅 1 个同步时点：交易日 21:00（晚间净值公布后，避免盘中获取半成品数据）
- 使用 `CronTrigger`，时区 `Asia/Shanghai`
- `max_instances=1`、`coalesce=True`、`misfire_grace_time=300s`

**同步任务流程**（`_run_sync`）：
1. 交易日判断（非交易日跳过）
2. 更新 LOF 清单（`discover_and_update`：发现新上市 / 清理退市）
3. 同步基金申购赎回信息
4. 增量数据同步（`DataSyncCore.sync_all()`）
5. 写入同步时间 + 同步报告到 `data/`
6. 数据质量检查（subprocess 调用 `data_quality_check.py`）

**API 查看**：`GET /api/v1/meta/scheduler` — 返回调度器运行状态和下次执行时间

### 4. LOF 清单自动维护 `scripts/discover_new_lof.py`

`discover_and_update()` 每天同步前自动运行：
- **数据源**：东方财富 LOF 实时行情（主源）+ 同花顺 LOF 列表（补充源）+ 基金类型映射
- **类型筛选**：剔除债券型、货币型、固收型、理财型、FOF-稳健型（无套利价值）；保留股票型、指数型、混合型、QDII、FOF-进取/均衡型
- **新上市发现**：市场有但清单没有 → 追加到 `all_LOF.txt`
- **退市清理**：清单有但市场没有 → 从 `all_LOF.txt` 移除，并删除对应 `data/lof_{code}.csv`

### 5. FastAPI 后端 `api/`

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/v1/opportunities` | GET | 机会列表，参数：`min_score`/`purchase_open`/`max_fee`/`min_purchase_limit`/`trade_commission`/`min_net_profit`/`limit` |
| `/api/v1/funds/{code}` | GET | 基金详情（评分 + 净利润 + 申购信息 + 历史摘要） |
| `/api/v1/funds/{code}/score` | GET | 仅评分 |
| `/api/v1/funds/{code}/history` | GET | 历史行情（`days` 参数，默认 60） |
| `/api/v1/meta/data-status` | GET | 数据同步状态（读取 `data/` 下的状态文件） |
| `/api/v1/meta/scheduler` | GET | 定时任务调度器状态（运行中/下次执行时间） |
| `/api/v1/meta/health` | GET | 健康检查 |
| `/docs` | GET | Swagger UI |

CORS 允许全部来源（局域网使用可接受；公网部署应收紧）。

### 6. 前端 `h5/`

**两套实现并存**：
- `h5/index.html` — 单文件 Vue 3 SPA（793 行），使用 `h5/vendor/` 下的本地 vue + vue-router（不依赖 CDN），已用 CSS 变量设计系统（neutral 主题），移动端 viewport 适配 + 触摸反馈 + 小屏适配。**生产部署直接用此文件**。
- `h5/src/` — Vite + Vue 3 SFC 工程化版本，功能较简化（缺少净利润展示、QDII 标签、T+2 风险等增强）。开发时 `npm run dev` 走 Vite，通过 `vite.config.js` 代理 `/api` 到 `localhost:8000`。

**页面**：
- 机会列表（`/opportunities`）— 筛选栏 + 风险提示 + 数据时间/滞后 + 基金卡片
- 基金详情（`/fund/:code`）— 评分 + 指标 + 申购信息 + 评分理由 + 风险提示
- 数据状态（`/status`）— 同步状态 + 盘中更新时点 + 免责声明

## 数据文件格式

> ⚠️ 所有运行时数据文件都在 `data/` 目录下，该目录已 gitignore，容器部署时作为数据卷挂载。

### `data/lof_{code}.csv`

集思录原始字段，UTF-8-SIG 编码：

| 字段 | 说明 |
|------|------|
| `fund_id` | 基金代码 |
| `price_dt` | 价格日期 |
| `price` | 场内价格 |
| `volume` | 成交量（万份） |
| `net_value` | 基金净值 |
| `est_val` | 盘中估值 |
| `discount_rt` | 溢价率（%，正=溢价，负=折价） |
| `amount` | 成交额（万元） |
| `amount_incr` | 场内份额增速（%） |
| `is_est` | 是否估值 |

### `data/fund_purchase_em_{YYYYMMDD}.csv`

东方财富 akshare `fund_purchase_em()` 输出，每日一份缓存。`fetch_fund_purchase.py` 会自动清理非当天的缓存文件。字段包括：`基金代码`/`基金简称`/`基金类型`/`申购状态`/`赎回状态`/`日累计限定金额`/`手续费`。`normalize_purchase_status()` 会将"限大额"按金额改写为"限购500"/"限购10万"等可读形式。

### 运行时生成文件

| 文件 | 说明 |
|------|------|
| `data/last_sync_time.txt` | 最后同步时间（北京时间） |
| `data/last_sync_report.json` | 同步报告（更新数、失败数、耗时、失败代码列表） |
| `data/data_quality_report.json` | 质量检查报告（新鲜度、完整性、异常值，状态 healthy/degraded/failed） |

## 部署方式

### Docker Compose（推荐，极空间 NAS）

```bash
# 修改 docker-compose.yml 中的 <YOUR_USER_ID> 为实际路径
sed -i 's/<YOUR_USER_ID>/你的实际ID/g' docker-compose.yml

# 构建并启动
docker-compose up -d --build

# 首次数据同步
docker exec lof-api python scripts/sync_daily.py

# 访问
# H5 页面: http://<NAS_IP>:18080
# API 文档: http://<NAS_IP>:18080/docs
```

架构：Nginx（端口 18080，托管 H5 静态文件 + 反向代理 API）→ FastAPI（容器内 8000）。数据卷挂载 `data/` 和 `logs/`。

详细部署指南见 [DEPLOY_ZSPACE.md](DEPLOY_ZSPACE.md)。

### 本地开发

```bash
# 后端
pip install -r requirements.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（Vite 开发版）
cd h5 && npm install && npm run dev    # http://localhost:5173，代理 /api 到 8000

# 手动同步数据
python scripts/sync_daily.py                    # 增量同步
python scripts/sync_daily.py --init             # 首次全量
python scripts/sync_daily.py --code 161725      # 单只
python scripts/sync_daily.py --verify           # 验证完整性

# 数据质量检查
python scripts/data_quality_check.py

# 抓取申购信息
python scripts/fetch_fund_purchase.py

# 发现新 LOF
python scripts/discover_new_lof.py

# 清理过期数据
python scripts/cleanup_old_data.py
python scripts/cleanup_old_data.py --days 90
```

## 开发约定

1. **时区**：所有时间逻辑用 `datetime.now(ZoneInfo("Asia/Shanghai"))`，不要用 `datetime.now()` 裸调用。
2. **项目根目录定位**：用 `get_project_root()` 模式（`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`），不要硬编码路径。
3. **数据目录**：所有运行时数据文件都放在 `data/` 下（已 gitignore）。新增数据文件路径统一通过 `get_project_root() + "data/"` 拼接。
4. **数据加载**：`LOFArbitrageAnalyzer.load_all_data()` 每次重新读盘，无缓存。API 每次请求都 new 一个 analyzer 实例。若需加缓存，应在 API 层做，不要在 analyzer 里引入 Streamlit 的 `@st.cache_data`。
5. **评分不含"胜率"措辞**：`score_to_signal` 使用"评分优秀/良好/中等/一般/不推荐"，避免合规风险。新增文案请保持"评分等级"措辞。
6. **申购状态解析**：`parse_purchase_limit()` 处理字符串；`is_purchase_open()` 判断；`get_purchase_block_reason()` 返回阻断原因。新增过滤条件应在这三个函数中扩展。
7. **净利润口径**：溢价套利扣申购费+佣金；折价套利扣赎回费+佣金。赎回费按持有期分档估计（T+2 套利默认 <7 天档 1.5%）。
8. **套利方向**：`arbitrage_direction` 字段为 `"premium"` 或 `"discount"`，前端和分析逻辑都应据此调整文案和颜色。
9. **QDII 处理**：通过 `fund_type` 字段识别，评分扣 10 分，前端应标记 QDII 标签并提示到账周期风险。
10. **CSV 编码**：写入用 `encoding='utf-8-sig'`（带 BOM，Excel 友好），读取用 `dtype=str` 保留代码前导零。
11. **前端两套实现**：修改 `h5/index.html`（生产）和 `h5/src/`（开发）时注意同步。新增强化功能优先更新 `h5/index.html`。
12. **定时任务**：调度器在 `core/scheduler.py`，注册在 `api/main.py` 的 lifespan 中。新增定时任务在 `SYNC_TIMES` 列表添加或在 `init_scheduler()` 中注册新 job。
13. **LOF 清单维护**：`all_LOF.txt` 由 `discover_new_lof.py` 自动维护，不要手动编辑。类型筛选规则在 `EXCLUDE_TYPE_KEYWORDS` 中配置。
14. **数据保留**：同步时自动清理超过 64 天的数据，如需调整修改 `scripts/cleanup_old_data.py` 中的 `DEFAULT_KEEP_DAYS`。
15. **数据时间提示**：盘中 T 日溢价率可能为估值或待确认状态（`is_est=True`），属正常现象，不应报为错误。若当日数据缺失会自动回退到 T-1（`is_t1_fallback=True`）。

## Git 信息

- Remote：`git@github.com:liamyu/lof-arbitrage.git`（fork 自 `skyz72432-max/lof-arbitrage`）
- 分支：`main`
- 定时同步：容器内 APScheduler，不依赖 GitHub Actions

## 版本演进

| 版本 | 主要变更 |
|------|---------|
| v2（当前） | 净利润计算、折价套利、QDII 识别、T+2 风险量化、交易佣金参数、APScheduler 容器内定时、Docker Compose 部署、自动发现新 LOF、数据自动清理 |
| v1 | FastAPI + Vue 3 H5、基础溢价套利评分、GitHub Actions 定时同步、申购状态硬性过滤 |
