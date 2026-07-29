# LOF 溢价套利监测系统

> **给 AI 助手的上下文说明**：本 README 是项目唯一权威结构文档，`PROJECT_STRUCTURE.md` 和 `OLD_FILES.md` 已过时，请以本文件为准。修改代码前请通读"核心模块"和"开发约定"两节。

## 项目简介

LOF（上市开放式基金）溢价套利监测系统。从集思录抓取全市场 LOF 的溢价率行情，从东方财富抓取基金申购状态，经评分引擎计算套利机会得分，通过 FastAPI REST API 和 Vue 3 移动端 H5 页面对外展示。数据同步由容器内定时任务在交易日盘中自动执行。

- **数据源**：集思录 `jisilu.cn`（LOF 溢价率行情）、东方财富 `akshare`（基金申购赎回状态）
- **后端**：FastAPI + Pandas + NumPy
- **前端**：Vue 3（单文件 CDN 版 `h5/index.html` + Vite SFC 版 `h5/src/`）
- **定时任务**：Docker 容器内 cron 定时执行 `sync_daily.py`（交易日盘中多个时点）
- **时区**：全链路使用 `Asia/Shanghai`

## 目录结构

```
lof-arbitrage/
├── api/                        # FastAPI 后端
│   ├── main.py                 # 应用入口，注册路由 + CORS
│   ├── models.py               # Pydantic 响应模型
│   └── routers/
│       ├── opportunities.py    # GET /api/v1/opportunities（机会列表）
│       ├── funds.py            # GET /api/v1/funds/{code}（详情/评分/历史）
│       └── meta.py             # GET /api/v1/meta/data-status（数据状态）
├── core/                       # 核心业务逻辑
│   ├── analyzer.py             # 评分引擎 LOFArbitrageAnalyzer
│   └── data_sync.py            # 数据同步器 DataSyncCore
├── utils/                      # 工具模块
│   ├── data_manager.py         # DataManager 数据读写验证
│   └── trading_calendar.py     # 交易日判断（上交所 SSE 日历）
├── scripts/                    # 运维脚本
│   ├── sync_daily.py           # 每日数据同步入口
│   ├── data_quality_check.py   # 数据质量检查
│   ├── fetch_fund_purchase.py  # 抓取基金申购信息（akshare）
│   ├── discover_new_lof.py     # 自动发现新上市LOF + 按类型筛选 + 清理退市
│   └── LOF_dashboard.py        # Streamlit 仪表板（遗留，不再维护）
├── h5/                         # 前端
│   ├── index.html              # 单文件 Vue 3 SPA（CDN，生产用）
│   ├── src/                    # Vite + Vue 3 SFC 版（开发用）
│   │   ├── views/{Opportunities,FundDetail,DataStatus}.vue
│   │   ├── api.js              # API 封装
│   │   ├── router.js           # 路由配置
│   │   └── main.js / App.vue
│   ├── package.json / vite.config.js
│   └── dist/                   # 构建产物（vite build）
├── data/                       # LOF 历史行情 CSV（由定时任务动态生成，不提交到仓库）
├── legacy/                     # 旧脚本归档（不再使用，仅供参考）
├── all_LOF.txt                 # LOF 代码清单（自动发现+类型筛选维护）
├── requirements.txt
├── .gitignore
└── README.md                   # 本文件
```

## 核心模块

### 1. 评分引擎 `core/analyzer.py`

`LOFArbitrageAnalyzer` 是纯数据服务类，无 Streamlit/UI 依赖。

**评分维度（总分 100）**：
- **溢价率维度**（权重 60%，最高 60 分）：当前溢价率绝对值、相对 5/10/15 日均值的偏离、近 3 日趋势、极端溢价区间加成、价格跌幅惩罚
- **流动性维度**（权重 50%，最高 40 分）：近 3 日成交额/份额是否达 1000 万阈值、份额增速稳定性、套利盘撤离信号

**评分等级**（`score_to_signal`）：≥80 评分优秀 / ≥65 评分良好 / ≥50 评分中等 / ≥35 评分一般 / <35 不推荐

**硬性过滤**（`get_purchase_block_reason`）：申购暂停/封闭期/认购期、限额为 0、限额过低（默认 <1000 元）、手续费过高（默认 >0.5%）

**关键方法**：
- `load_all_data()` — 加载 `data/lof_*.csv`，用估值 `est_val` 回填缺失的 `discount_rt`
- `load_purchase_info()` — 加载 `fund_purchase_em_*.csv` 申购信息
- `score_one_lof(lof_data, code)` — 单只 LOF 评分
- `get_all_signals()` — 全市场评分，按分数降序
- `get_opportunities(min_score, purchase_open, max_fee, min_purchase_limit)` — 过滤后的机会列表
- `get_fund_detail(code)` — 单只详情（含历史摘要）

### 2. 数据同步 `core/data_sync.py`

`DataSyncCore` 处理集思录 API 的 50 条滚动窗口限制，支持：
- 请求限流（`request_interval` 默认 0.5s）
- 带指数退避的重试（`max_retries` 默认 3）
- 增量合并：新增记录 + 更新已有记录中溢价率为空/"-"的行
- 响应与记录级别的数据校验

### 3. FastAPI 后端 `api/`

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/v1/opportunities` | GET | 套利机会列表，支持 `min_score`/`purchase_open`/`max_fee`/`min_purchase_limit`/`limit` |
| `/api/v1/funds/{code}` | GET | 基金详情（评分 + 申购信息 + 历史摘要） |
| `/api/v1/funds/{code}/score` | GET | 仅评分 |
| `/api/v1/funds/{code}/history` | GET | 历史行情（`days` 参数，默认 60） |
| `/api/v1/meta/data-status` | GET | 数据同步状态（读取 `last_sync_time.txt` + `data_quality_report.json`） |
| `/api/v1/meta/health` | GET | 健康检查 |
| `/docs` | GET | Swagger UI |

CORS 允许全部来源（生产环境应收紧）。

### 4. 前端 `h5/`

**两套实现并存**：
- `h5/index.html` — 单文件 Vue 3 SPA（CDN 引入 vue@3.4 + vue-router@4.2），内联 CSS/JS，**生产部署直接用此文件**。已做移动端 viewport 适配、触摸反馈、小屏（≤380px）适配。
- `h5/src/` — Vite + Vue 3 SFC 工程化版本，功能较简化（缺少申购状态标签、手续费/限额过滤输入框等增强）。开发时 `npm run dev` 走 Vite，通过 `vite.config.js` 代理 `/api` 到 `localhost:8000`。

**页面**：
- 机会列表（`/opportunities`）— 筛选栏 + 风险提示横幅 + 数据时间/滞后 + 基金卡片列表
- 基金详情（`/fund/:code`）— 评分大圆 + 指标网格 + 申购信息 + 评分理由 + 数据概览 + 风险提示
- 数据状态（`/status`）— 同步状态徽章 + 信息网格 + 盘中更新时点 + 免责声明

## 数据文件格式

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

### `fund_purchase_em_{YYYYMMDD}.csv`

东方财富 akshare `fund_purchase_em()` 输出，每日一份缓存。`fetch_fund_purchase.py` 会自动清理非当天的缓存文件。字段：`基金代码`/`基金简称`/`申购状态`/`赎回状态`/`日累计限定金额`/`手续费`。`normalize_purchase_status()` 会将"限大额"按金额改写为"限购500"/"限购10万"等可读形式。

### 运行时生成文件（已 gitignore）

- `data/last_sync_time.txt` — 最后同步时间（北京时间）
- `data/last_sync_report.json` — 同步报告（更新数、失败数、耗时）
- `data/data_quality_report.json` — 质量检查报告（新鲜度、完整性、异常值，状态 healthy/degraded/failed）

## 容器定时任务

数据同步由 Docker 容器内的 cron 定时任务执行，不依赖 GitHub Actions。交易日盘中多个时点自动运行 `sync_daily.py`，数据直接写入容器挂载的 `data/` 目录，无需推送到代码仓库。

## 开发命令

```bash
# 后端
pip install -r requirements.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# 或
python api/main.py

# 前端（Vite 开发版）
cd h5 && npm install && npm run dev    # http://localhost:5173，代理 /api 到 8000

# 前端构建
cd h5 && npm run build                 # 产物在 h5/dist/

# 手动同步数据
python scripts/sync_daily.py                    # 增量同步
python scripts/sync_daily.py --init             # 首次全量
python scripts/sync_daily.py --code 161725      # 单只
python scripts/sync_daily.py --verify           # 验证完整性

# 数据质量检查
python scripts/data_quality_check.py

# 抓取申购信息
python scripts/fetch_fund_purchase.py
```

## 开发约定

1. **时区**：所有时间逻辑用 `datetime.now(ZoneInfo("Asia/Shanghai"))`，不要用 `datetime.now()` 裸调用。
2. **项目根目录定位**：用 `core/analyzer.py` 中的 `get_project_root()` 模式（`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`），不要硬编码路径。
3. **数据加载**：`LOFArbitrageAnalyzer.load_all_data()` 每次重新读盘，无缓存。API 每次请求都 new 一个 analyzer 实例。若需加缓存，应在 API 层做，不要在 analyzer 里引入 Streamlit 的 `@st.cache_data`。
4. **评分不含"胜率"措辞**：`score_to_signal` 已从"极高胜率/高胜率"改为"评分优秀/评分良好"等，避免合规风险。新增文案请保持"评分等级"措辞。
5. **申购状态解析**：`parse_purchase_limit()` 处理"限购100万"/"无限制"等字符串；`is_purchase_open()` 判断是否可申购；`get_purchase_block_reason()` 返回阻断原因或 None。新增过滤条件应在这三个函数中扩展。
6. **CSV 编码**：写入用 `encoding='utf-8-sig'`（带 BOM，Excel 友好），读取用默认或 `dtype=str` 保留代码前导零。
7. **前端两套实现**：修改 `h5/index.html`（生产）和 `h5/src/`（开发）时注意同步。`h5/src/` 版本功能较简化，新增强化功能时应优先更新 `h5/index.html`。
8. **legacy/ 目录**：旧脚本归档，不再维护，不要从中导入。`scripts/LOF_dashboard.py` 是 Streamlit 遗留仪表板，评分逻辑已迁移到 `core/analyzer.py`。
9. **数据时间提示**：盘中 T 日溢价率可能为估值或待确认状态（`is_est=True`），属正常现象，不应报为错误。

## 数据现状

- 最新数据日期：2026-07-28，滞后 0 天
- LOF 总数：262 只
- 数据质量状态：healthy
- 详见 `last_sync_report.json` 和 `data_quality_report.json`

## Git 信息

- Remote：`git@github.com:liamyu/lof-arbitrage.git`（fork 自 `skyz72432-max/lof-arbitrage`）
- 分支：`main`
