#!/bin/bash
set -e

echo "Starting AI Meeting Backend..."

# 初始化数据库
echo "Initializing database..."
python scripts/init_db.py

# 启动应用
echo "Starting application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
