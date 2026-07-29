# LOF 套利工具 - API 服务镜像
FROM python:3.11-alpine

WORKDIR /app

# 安装编译依赖并清理缓存
RUN apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    linux-headers \
    && rm -rf /var/cache/apk/*

# 复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache/pip

# 复制项目代码
COPY . .

# 暴露 API 端口
EXPOSE 8000

# 启动 FastAPI 服务
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
