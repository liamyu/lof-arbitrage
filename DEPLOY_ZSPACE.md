# 极空间 Docker 一键部署指南

## 架构说明

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   浏览器     │─────▶│  Nginx:8080 │─────▶│  FastAPI    │
│  (手机/PC)   │      │  前端+代理   │      │  后端:8000  │
└─────────────┘      └─────────────┘      └─────────────┘
                              │                    │
                              ▼                    ▼
                        ./h5 (静态文件)      ./data (持久化数据)
```

- **Nginx**: 对外暴露 8080 端口，托管 H5 前端页面，同时反向代理 API 请求到后端
- **FastAPI**: 提供 REST API，处理评分计算、数据查询
- **数据卷**: `./data` 目录持久化 LOF 历史行情数据

## 前置条件

1. 极空间 NAS 已开启 Docker 功能
2. 已安装 Docker Compose（极空间 Docker 应用自带）
3. 保证 NAS 能访问外网（同步数据需要从集思录等站点拉取）

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
   - 浏览器访问 `http://<极空间IP>:8080`
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

## 首次数据同步

部署完成后，需要手动执行一次数据同步来填充历史数据：

```bash
# 进入 API 容器执行同步
docker exec lof-api python scripts/sync_daily.py
```

或在极空间 Docker 界面中：
1. 找到 `lof-api` 容器
2. 点击「终端」
3. 执行 `python scripts/sync_daily.py`

同步完成后，页面即可正常显示套利机会。

## 定时自动同步（推荐）

极空间支持「计划任务」功能：

1. 打开极空间「计划任务」应用
2. 新建任务，类型选择「脚本」
3. 执行命令：
   ```bash
   docker exec lof-api python scripts/sync_daily.py
   ```
4. 设置定时规则：
   - 交易日：每天 15:30（收盘后）
   - 频率：每周一至周五

或在容器内配置 cron（需修改 Dockerfile 添加 cron 支持）。

## 目录说明

极空间 Docker 的目录格式为 `/tmp/zfsv3/nvme12/<YOUR_USER_ID>/data/docker/lof/...`，其中 `<YOUR_USER_ID>` 是你的极空间用户 ID（通过 `ls /tmp/zfsv3/nvme12/` 查看）。

| 本地路径 | 容器内路径 | 说明 |
|---------|-----------|------|
| `.../lof/data` | `/app/data` | LOF 历史行情数据（需持久化） |
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

# 手动触发数据同步
docker exec lof-api python scripts/sync_daily.py

# 数据质量检查
docker exec lof-api python scripts/data_quality_check.py
```

## 故障排查

### 页面打开空白或 API 报错
1. 检查容器是否都在运行：`docker-compose ps`
2. 查看 API 日志：`docker-compose logs api`
3. 确认 `data` 目录有数据文件（至少有一个 `lof_*.csv`）

### 端口冲突
如果 8080 端口已被占用，修改 `docker-compose.yml` 中的端口映射，如改为 `18080:80`。

### 数据同步失败
1. 确认 NAS 能访问外网（集思录网站）
2. 检查是否有代理/VPN 影响
3. 查看同步日志：`docker-compose logs api | grep sync`

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
