#!/bin/bash
# LOF 套利工具 - 极空间 Docker 一键部署脚本

set -e

echo "========================================"
echo "  LOF 套利工具 Docker 部署脚本"
echo "========================================"

# 检查 docker 和 docker-compose
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose 未安装"
    exit 1
fi

echo ""
echo "[1/4] 停止旧容器（如果存在）..."
docker-compose down 2>/dev/null || true

echo ""
echo "[2/4] 构建并启动服务..."
docker-compose up -d --build

echo ""
echo "[3/4] 等待服务启动..."
sleep 5

# 检查服务健康状态
echo ""
echo "[4/4] 检查服务状态..."
if docker-compose ps | grep -q "Up"; then
    echo "服务状态: 运行正常"
    echo ""
    echo "访问地址:"
    echo "  - H5 页面:    http://$(hostname -I | awk '{print $1}'):8080"
    echo "  - API 文档:   http://$(hostname -I | awk '{print $1}'):8080/docs"
    echo "  - 健康检查:   http://$(hostname -I | awk '{print $1}'):8080/api/v1/health"
    echo ""
    echo "========================================"
    echo "首次使用请先执行数据同步："
    echo "  docker exec lof-api python scripts/sync_daily.py"
    echo "========================================"
else
    echo "警告: 服务可能未正常启动，请检查日志："
    echo "  docker-compose logs"
    exit 1
fi
