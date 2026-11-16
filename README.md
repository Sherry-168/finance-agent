# 个人记账与消费分析 AI 助手

> 2026 GDUF-AI-Studio 考核项目 · 选题 A
> 一句话：**说一句话、拍一张照，钱就记好了；问一句话，答案就出来了。**

## 项目简介

面向个人日常消费记录与分析：把「录入一笔账要点击五六次」压成「一句话 / 一张小票」，
把「查一个数要翻筛选器」压成「随口一问」。

核心设计原则：**LLM 只做理解和生成，所有算账、统计、预算判断一律由 Python + SQL 完成。**
模型输出结构化槽位，金额换算、时间区间、SUM/COUNT、预算比较全部走代码，杜绝模型算错账。

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Gradio 6 + 自定义 CSS + ECharts | 五区界面：记账对话 / 明细 / 统计 / 预算 / 演示 |
| 后端 | Python 3.11+ · FastAPI · Uvicorn | `/api/v1`，统一响应包装 `{code, message, data}` |
| 数据 | SQLite（标准库 sqlite3） | 金额以「分」整数存储，避免浮点误差 |
| LLM | OpenAI 兼容接口（DeepSeek / Qwen / GLM 任选） | 仅用于槽位解析与分类，不参与算数 |
| OCR | 视觉模型 API 优先 + PaddleOCR 本地兜底 | 无 Key 也能跑通图片链路（第二周接入） |
| 容器 | Docker · docker-compose | 一条命令起后端 + 前端 |

## 目录结构

```
finance-agent/
├── app/                    # 后端应用（FastAPI）
│   ├── main.py             # 应用装配：生命周期建库、全局异常处理、路由注册
│   ├── core/               # 基础设施
│   │   ├── config.py       # 环境变量集中读取（唯一配置入口）
│   │   ├── response.py     # 统一响应包装与业务错误码
│   │   └── db.py           # SQLite 连接生命周期 + 启动建表
│   └── routers/            # HTTP 路由，按业务域拆分
│       ├── health.py       # 健康检查
│       ├── records.py      # 记账解析 / 确认入库
│       └── query.py        # 自然语言查账
├── db/                     # 数据层：建表 SQL + DAO（不裸写 SQL）
├── logic/                  # 规则层：金额换算、分类词典、统计、预算、时间解析（纯函数）
├── frontend/               # Gradio 前端（api 客户端 / ui 组件 / 五个 Tab）
├── scripts/                # 演示数据导入、自检脚本
├── tests/                  # pytest 用例（数据层与规则层）
├── docs/                   # 接口契约、数据库设计、评审问题清单
├── data/                   # SQLite 文件与示例账单（容器内挂载为数据卷）
├── Dockerfile
├── docker-compose.yml
├── main.py                 # 兼容入口：uvicorn main:app / python main.py
├── requirements.txt
└── .env.example
```

## 快速启动（Docker，推荐）

```bash
# 1. （可选）配置密钥，不配也能启动，只是解析走规则兜底
cp .env.example .env        # Windows: copy .env.example .env

# 2. 构建并启动后端 + 前端
docker compose up --build
```

启动后：

| 地址 | 说明 |
|---|---|
| http://localhost:7860 | 前端界面（Gradio） |
| http://localhost:8000/api/v1/health | 后端健康检查 |
| http://localhost:8000/docs | FastAPI 自动生成的接口文档 |

停止与清理：

```bash
docker compose down          # 停止并移除容器
docker compose down -v       # 同时清空数据卷（慎用）
```

**首次启动会自动建表**（`records` / `categories` / `budgets` / `sessions`）并写入 8 类分类词典，无需手动执行 SQL。

## 本地开发（不使用 Docker）

```bash
# 1. 安装依赖（建议在虚拟环境中）
pip install -r requirements.txt
pip install -r frontend/requirements.txt

# 2. 配置环境变量
cp .env.example .env        # Windows: copy .env.example .env

# 3. 启动后端（项目根目录）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 另开一个终端启动前端（frontend 目录）
cd frontend && python app.py
```

## 环境变量

全部通过环境变量或 `.env` 注入，**真实密钥不得提交到仓库**（`.env` 已在 `.gitignore` 中）。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | 空 | OpenAI 兼容接口密钥；为空时解析降级到规则兜底 |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | 换供应商只改这里 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `OCR_PROVIDER` | `local` | `api` = 视觉模型优先，`local` = PaddleOCR 本地兜底 |
| `DB_PATH` | `data/finance.db` | 相对项目根目录；容器内为 `/app/data/finance.db` |
| `DEFAULT_USER_ID` | `demo_user` | 单用户简化，预留多用户字段 |
| `BACKEND_HOST` / `BACKEND_PORT` | `0.0.0.0` / `8000` | 后端监听地址 |
| `API_BASE_URL` | `http://localhost:8000/api/v1` | 前端请求后端的地址；**容器内由 compose 覆盖为 `http://backend:8000/api/v1`** |
| `MOCK_FALLBACK` | `1` | 后端不可达时前端是否降级本地 Mock |

## 端口与数据持久化

| 项 | 值 | 说明 |
|---|---|---|
| 后端端口 | `8000` | 容器 `8000:8000` |
| 前端端口 | `7860` | 容器 `7860:7860` |
| 数据挂载 | 宿主机 `./data` ⇄ 容器 `/app/data` | SQLite 文件 `/app/data/finance.db` |
| 持久化效果 | 容器重建、升级镜像不丢数据 | 示例账单 `data/sample_transactions.csv` 同在此目录 |

> 容器以 root 运行：评审多为 bind mount 宿主机目录，非 root 用户在 Linux 上会因目录属主无法写入 `finance.db`，
> 可复现性优先于容器内最小权限。原因写在 `Dockerfile` 注释里。

## 测试

```bash
python scripts/selfcheck.py     # 不依赖 pytest，跑一遍规则层与 DAO 往返
pytest tests/ -v                # 单元测试
```

## 当前进度（第一周 Day 2）

| 能力 | 状态 | 说明 |
|---|---|---|
| 健康检查 | 已实现 | `/api/v1/health` 与 `/health` 等价，实测通过 |
| 统一响应包装 / 全局异常处理 | 已实现 | 参数错误 `1001`、资源不存在 `1002` 均返回统一包装 |
| 启动自动建表 | 已实现 | 首次启动建 4 张表并初始化 8 类 |
| 自然语言记账 `/records/parse` | 接口就绪 | 返回契约示例数据，解析模块待接入（Day 3） |
| 确认入库 `POST /records` | 接口就绪 | 尚未落库（Day 3 接 DAO） |
| 自然语言查账 `/query` | 入参已修 | 已按契约收 `question`（原实现会 422）；槽位与聚合待 Day 5 |
| 明细 CRUD / 统计 / 预算 / 演示数据 | 待实现 | Day 4–6 |
| 小票 OCR | 待实现 | 第二周 |
| Docker 镜像 | 已提供 | 本机未安装 Docker，尚未实测 `docker compose up --build` |

## 团队分工

| 成员 | 负责 |
|---|---|
| 史雅萱 | 后端与工程化（队长）：FastAPI 接口、容器化、接口契约 |
| 李语琛 | AI 核心：记账解析与查账槽位解析、澄清反问、Prompt 设计 |
| 蔡适伶 | 数据与规则：建表、分类词典、统计 SQL、预算预警 |
| 林丹苗 | 前端：Gradio 界面、图表、对接接口 |
| 江为 | 测试与交付：示例账单、小票素材、测试用例、README 与答辩材料 |

> 启动命令以本文与仓库实际文件为准；后续接口变更请先改 `docs/api.md` 再改代码。
