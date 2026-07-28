# LOF 套利工具 - API 服务镜像
FROM python:3.11-slim

WORKDIR /app

# 安装编译依赖（numpy/pandas 等需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露 API 端口
EXPOSE 8000

# 启动 FastAPI 服务
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
