# 极空间 Docker 一键部署指南

## 架构说明

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   浏览器     │─────▶│  Nginx:80   │─────▶│  FastAPI    │
│  (手机/PC)   │      │  前端+代理   │      │  后端:8000  │
└─────────────┘      └──────┬──────┘      └──────┬──────┘
                            │                    │
                            ▼                    ▼
                      ./h5 (静态文件)      ./data (持久化数据)
                                                  │
                                                  ▼
                                           APScheduler
                                        交易日 21:00 自动同步
```

- **Nginx**: 对外暴露端口（默认 18080），托管 H5 前端页面，反向代理 API 请求到后端
- **FastAPI**: 提供 REST API，处理评分计算、数据查询
- **APScheduler**: 容器内定时任务调度器，交易日 21:00 自动执行数据同步（无需外部 cron）
- **数据卷**: `./data` 目录持久化 LOF 历史行情、申购信息、同步状态等数据

## 前置条件

1. 极空间 NAS 已开启 Docker 功能
2. 已安装 Docker Compose（极空间 Docker 应用自带）
3. 保证 NAS 能访问外网（同步数据需要从集思录、东方财富等站点拉取）

## 部署步骤

### 方法一：极空间 Docker 图形界面导入（推荐）

1. **下载项目代码**
   - 在极空间文件管理器中，进入你想存放项目的目录（如 `/volume1/docker/`）
   - 使用 Git 克隆或手动上传项目文件

2. **修改路径占位符（必须）**
   编辑 `docker-compose.yml`，将所有 `<YOUR_USER_ID>` 替换为你的极空间实际用户 ID。

   获取方式：在极空间 SSH 中执行以下命令查看你的真实路径：
   ```bash
   ls /tmp/zfsv3/nvme12/
   ```
   输出示例：`12345678901`，将这个值替换掉所有 `<YOUR_USER_ID>`。

   如果你使用 VS Code 或 sed，可以一键替换：
   ```bash
   sed -i 's/<YOUR_USER_ID>/你的实际ID/g' docker-compose.yml
   ```

3. **修改端口（可选）**
   编辑 `docker-compose.yml`，将 `18080:80` 中的 `18080` 改为你想用的端口：
   ```yaml
   ports:
     - "18080:80"
   ```

4. **极空间 Docker 中创建 Compose 项目**
   - 打开极空间 Docker 应用
   - 点击「Compose」→「创建项目」
   - 项目名称填 `lof-arbitrage`
   - 选择项目路径为你存放代码的目录
   - 点击「创建并启动」

5. **等待构建完成**
   - 首次构建需要下载 Python 基础镜像并安装依赖，约 3-5 分钟
   - 构建完成后，两个容器都会显示「运行中」

6. **访问服务**
   - 浏览器访问 `http://<极空间IP>:18080`
   - 手机访问同理，确保手机和 NAS 在同一局域网

### 方法二：SSH 命令行部署

如果你的极空间已开启 SSH，可以远程执行：

```bash
# 1. 进入项目目录
cd /volume1/docker/lof-arbitrage

# 2. 一键启动
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

## 首次数据初始化

部署完成后，容器内的 APScheduler 会在下一个交易日 21:00 自动执行首次同步。在此之前页面数据为空，建议手动执行初始化：

```bash
# 1. 更新 LOF 清单（自动发现全市场 LOF、筛选类型、清理退市）
docker exec lof-api python scripts/discover_new_lof.py

# 2. 抓取基金申购赎回信息
docker exec lof-api python scripts/fetch_fund_purchase.py

# 3. 同步历史行情数据
docker exec lof-api python scripts/sync_daily.py --init

# 4. 数据质量检查
docker exec lof-api python scripts/data_quality_check.py
```

或在极空间 Docker 界面中：
1. 找到 `lof-api` 容器
2. 点击「终端」
3. 依次执行上述命令

同步完成后，页面即可正常显示套利机会。

## 定时自动同步（内置，无需额外配置）

容器启动后，APScheduler 自动在后台运行：

- **同步时点**：交易日 21:00（晚间净值公布后，避免盘中获取半成品估值数据）
- **同步内容**：
  1. 更新 LOF 清单（发现新上市 / 清理退市）
  2. 抓取基金申购赎回信息
  3. 增量同步历史行情数据
  4. 写入同步报告
  5. 数据质量检查
- **非交易日**：自动跳过，不执行同步

**查看调度器状态**：
```bash
docker exec lof-api curl -s http://localhost:8000/api/v1/meta/scheduler | python -m json.tool
```

或在浏览器中访问 `http://<NAS_IP>:18080/api/v1/meta/scheduler`。

> **注意**：无需配置极空间计划任务或 cron，所有定时逻辑已在容器内自动处理。

## 目录说明

极空间 Docker 的目录格式为 `/tmp/zfsv3/nvme12/<YOUR_USER_ID>/data/docker/lof/...`，其中 `<YOUR_USER_ID>` 是你的极空间用户 ID（通过 `ls /tmp/zfsv3/nvme12/` 查看）。

| 本地路径 | 容器内路径 | 说明 |
|---------|-----------|------|
| `.../lof/data` | `/app/data` | LOF 历史行情、申购信息、同步状态（需持久化） |
| `.../lof/logs` | `/app/logs` | 同步日志 |
| `.../lof/h5` | `/usr/share/nginx/html` | H5 前端页面 |
| `.../lof/nginx.conf` | `/etc/nginx/conf.d/default.conf` | Nginx 配置文件 |

## 常用维护命令

```bash
# 查看容器状态
docker-compose ps

# 查看 API 日志
docker-compose logs -f api

# 查看 Nginx 日志
docker-compose logs -f nginx

# 重启服务
docker-compose restart

# 重建镜像（代码更新后）
docker-compose up -d --build

# 进入 API 容器调试
docker exec -it lof-api bash

# 手动触发数据同步（全部流程）
docker exec lof-api python scripts/discover_new_lof.py
docker exec lof-api python scripts/fetch_fund_purchase.py
docker exec lof-api python scripts/sync_daily.py

# 数据质量检查
docker exec lof-api python scripts/data_quality_check.py

# 清理过期数据（保留 64 天，自动执行，可手动触发）
docker exec lof-api python scripts/cleanup_old_data.py

# 查看调度器状态
docker exec lof-api curl -s http://localhost:8000/api/v1/meta/scheduler

# 查看数据状态
docker exec lof-api curl -s http://localhost:8000/api/v1/meta/data-status
```

## 故障排查

### 页面打开空白或 API 报错
1. 检查容器是否都在运行：`docker-compose ps`
2. 查看 API 日志：`docker-compose logs api`
3. 确认 `data` 目录有数据文件（至少有一个 `lof_*.csv`）

### 数据滞后或未更新
1. 检查调度器状态：`docker exec lof-api curl -s http://localhost:8000/api/v1/meta/scheduler`
2. 查看是否为非交易日（非交易日不执行同步）
3. 手动触发同步：`docker exec lof-api python scripts/sync_daily.py`
4. 检查数据质量：`docker exec lof-api python scripts/data_quality_check.py`

### 端口冲突
如果 18080 端口已被占用，修改 `docker-compose.yml` 中的端口映射，如改为 `28080:80`。

### 数据同步失败
1. 确认 NAS 能访问外网（集思录 `jisilu.cn`、东方财富）
2. 检查是否有代理/VPN 影响
3. 查看同步日志：`docker-compose logs api | grep sync`
4. 单只基金测试：`docker exec lof-api python scripts/sync_daily.py --code 161725`

### 容器健康检查失败
健康检查路径为 `/api/v1/meta/health`。如果健康检查持续失败：
1. 检查 API 是否启动完成（首次启动需等待依赖安装）
2. 查看 API 容器日志：`docker-compose logs api`
3. 手动测试：`docker exec lof-api curl http://localhost:8000/api/v1/meta/health`

## 更新升级

当代码有更新时：

```bash
# 拉取最新代码
git pull

# 重建并重启
docker-compose up -d --build
```

## 安全提示

- 当前 CORS 配置为 `allow_origins=["*"]`，仅在局域网使用无风险
- 如需公网访问，建议：
  1. 修改 `api/main.py` 中的 CORS 为指定域名
  2. 配置 HTTPS（极空间自带外网访问可自动处理）
  3. 设置访问密码或反向代理鉴权
