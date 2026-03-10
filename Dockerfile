# 使用 Python 3.12 官方镜像
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY event_framework/ ./event_framework/
COPY main.py ./

# 创建非 root 用户运行服务
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 默认启动命令（可通过 docker run 覆盖）
CMD ["python", "main.py"]
