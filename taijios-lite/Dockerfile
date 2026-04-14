FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 数据目录（挂载点）
RUN mkdir -p /app/data/evolution /app/data/bot_users

ENV PYTHONUTF8=1
ENV PYTHONUNBUFFERED=1

# 默认启动 Telegram bot，可通过 command 覆盖
CMD ["python", "bot_telegram.py"]
