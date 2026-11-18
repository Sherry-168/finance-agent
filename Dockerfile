# 记账助手 · 应用镜像
# 同一镜像同时承载两个服务，由 docker-compose.yml 用不同 command 启动：
#   backend  → uvicorn app.main:app  (8000)
#   frontend → python frontend/app.py (7860)
#
# 说明（评审环境优先，取舍理由写在此处，便于答辩解释）：
# - 基础镜像 python:3.11-slim：体积小、无需编译；依赖多为纯 wheel，构建快。
# - 安装 tzdata：slim 默认 UTC，缺时区数据会让 date.today() 在北京时间 0~8 点算成前一天，
#   直接导致「本月/上月」查账区间错位。
# - 容器以 root 运行：评审多用 `./data` 挂载宿主机目录，非 root 用户在 Linux 上会因
#   目录属主写不进 finance.db。可复现性优先于容器内最小权限。
# - 健康检查用 python 标准库而非 curl：slim 镜像不带 curl。

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    DB_PATH=/app/data/finance.db

WORKDIR /app

# 依赖单独一层：只改业务代码不会触发重装。
# 两份 requirements 同名，拷到 /tmp 下改名安装，避免覆盖。
COPY requirements.txt /tmp/backend-requirements.txt
COPY frontend/requirements.txt /tmp/frontend-requirements.txt
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --upgrade pip \
 && pip install -r /tmp/backend-requirements.txt -r /tmp/frontend-requirements.txt \
 && rm -f /tmp/backend-requirements.txt /tmp/frontend-requirements.txt

COPY . .

# 数据目录固定 /app/data，compose 挂载到宿主机 ./data 持久化
RUN mkdir -p /app/data

EXPOSE 8000 7860

# 健康检查不写在镜像里：本镜像被两个服务复用，探针端口各不相同
# （backend 探 8000，frontend 跑 7860）。写死在此会让前端容器永远显示 unhealthy，
# 因此统一在 docker-compose.yml 的 backend 服务内声明。

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
