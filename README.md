# 个人记账与消费分析 AI 助手（Finance Agent）

> 2026 GDUF AI Studio 考核项目 · 选题 A
>
> 一句话：**说一句话、拍一张照，钱就记好了；问一句话，答案就出来了。**

## 1. 项目说明（Project Description）

* **做了什么**：面向个人日常消费记录与分析的智能记账助手，用户可通过自然语言或上传账单截图，快速完成记账。
* **面向场景**：把「录入一笔账要点击五六次」压成「一句话 / 一张小票」，把「查一个数要翻筛选器」压成「随口一问」，解决传统手动记账繁琐、分类困难的问题。
* **设计原则**：**LLM 只做理解和生成，所有算账、统计、预算判断一律由 Python + SQL 完成。** 模型输出结构化槽位，金额换算、时间区间、SUM/COUNT、预算比较全部走代码，杜绝模型算错账。

## 2. 技术栈与架构简述（Brief description of technical line and architecture）

* **前端**：Gradio 6 + 自定义 CSS + ECharts（五区界面：记账对话 / 明细 / 统计 / 预算 / 演示）
* **后端**：Python 3.11+ · FastAPI · Uvicorn（`/api/v1`，统一响应包装 `{code, message, data}`）
* **数据**：SQLite（标准库 sqlite3，金额以「分」整数存储，避免浮点误差）
* **AI 核心**：Dify 工作流（Workflow）+ DeepSeek 多模态视觉大模型
* **部署**：Docker · docker-compose（一条命令启动后端 + 前端）

## 3. AI 核心模块说明（Description of AI core module）

本项目核心 AI 驱动层采用 **Dify 工作流** 搭建，接入 **DeepSeek 多模态视觉大模型**。

### 核心功能（Core Functions）

* **自然语言输入**：支持直接输入一句话（如“打车花了25块”），AI 自动提取结构化数据。
* **多模态图片识别**：支持上传购物小票、外卖订单、淘宝账单截图，AI 直接读取图片内容。
* **多笔账单拆分**：遇到包含多笔消费的长截图，AI 可精准拆分为 JSON 数组（Array）形式输出。
* **结构化输出（JSON）**：通过严格的 Prompt 约束，强制大模型输出标准的 JSON 格式，方便后端直接解析入库。

### 数据输出示例（多笔图片识别）

```json
[
  {
    "amount": 16.01,
    "category": "购物",
    "description": "meiji明治雪吻夹心巧克力29g*2盒",
    "date": "11-10"
  },
  {
    "amount": 159,
    "category": "购物",
    "description": "RK R75Pro客制化无线机械键盘",
    "date": "11-10"
  }
]
```

## 4. 目录结构（Directory Structure）

```text
finance-agent/
├── app/                    # 后端应用（FastAPI）
│   ├── main.py             # 应用装配：生命周期建库、全局异常处理、路由注册
│   ├── core/               # 基础设施：配置、响应包装、数据库连接
│   └── routers/            # HTTP 路由：health / records / query
├── db/                     # 数据层：建表 SQL + DAO
├── logic/                  # 规则层：金额换算、分类词典、统计、预算（纯函数）
├── frontend/               # Gradio 前端（api 客户端 / ui 组件 / Tab）
├── scripts/                # 演示数据导入、自检脚本
├── tests/                  # pytest 用例（数据层与规则层）
├── docs/                   # 接口契约、数据库设计、评审问题清单
├── data/                   # SQLite 文件与示例账单（容器内挂载为数据卷）
├── Dockerfile
├── docker-compose.yml
├── main.py                 # 兼容入口：uvicorn main:app
├── requirements.txt
└── .env.example
```

## 5. 快速启动（Quick Start）

### Docker 方式（推荐）

```bash
# 1. 配置密钥
cp .env.example .env        # Windows 用户请手动复制并重命名

# 2. 构建并启动后端 + 前端
docker compose up --build
```

启动后访问：

* **前端界面**：http://localhost:7860/
* **后端健康检查**：http://localhost:8000/api/v1/health
* **后端接口文档**：http://localhost:8000/docs

> 数据持久化：项目使用 Docker 命名卷挂载 SQLite 数据文件，执行 `docker compose down` 后数据不会丢失；如需清空数据卷请执行 `docker compose down -v`。

### 本地开发（不使用 Docker）

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install -r frontend/requirements.txt

# 2. 配置环境变量
cp .env.example .env

# 3. 启动后端（项目根目录）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 另开终端启动前端
cd frontend && python app.py
```

## 6. 环境变量（Environment Variables）

| 变量 | 默认值 | 说明 |
|---|---|---|
| LLM_API_KEY | 空 | Dify 接口或大模型 API 密钥 |
| LLM_BASE_URL | https://api.deepseek.com/v1 | API 地址 |
| DB_PATH | data/finance.db | SQLite 数据库路径 |
| API_BASE_URL | http://localhost:8000/api/v1 | 前端请求后端的地址（容器内自动覆盖为 http://backend:8000） |

> 真实密钥不得提交到仓库（`.env` 已在 `.gitignore` 中）。

## 7. 当前进度（第一周）（Current Progress）

| 能力 | 状态 | 说明 |
|---|---|---|
| 健康检查 / 统一响应包装 | 已实现 | `/api/v1/health` 返回标准 `{code, message, data}` |
| 启动自动建表 | 已实现 | 首次启动自动建 4 张表并初始化分类字典 |
| AI 核心 Dify 工作流 | 测试中 | 云端已搭建并跑通多模态测试，待封装为 Python 接口 |
| 自然语言记账 /records/parse | 接口就绪 | 待接入 Dify 解析 |
| 自然语言查账 /query | 接口就绪 | 槽位与聚合逻辑待联调 |
| 前端 Gradio 界面 | 已实现 | 基础框架与图表展示已打通 |
| 小票 OCR 识别 | 开发中 | Dify 多模态测试成功，待接入后端 |

## 8. 团队分工（Team Division）

| 成员 | 负责内容 |
|---|---|
| 史雅萱 | 后端与工程化（队长）：FastAPI 接口开发、Docker 容器化、接口契约制定、Git 合并 |
| 李语琛 | AI 核心：Dify 工作流搭建、Prompt 设计、多模态图片识别、结构化解析 |
| 蔡适伶 | 数据与规则：SQLite 建表、分类词典维护、统计 SQL 编写、预算预警逻辑 |
| 林丹苗 | 前端：Gradio 界面开发、图表可视化、前后端接口联调 |
| 江为 | 测试与交付：示例账单数据准备、测试用例编写、README 维护、答辩 PPT 与演示视频 |

> 启动命令以本文与仓库实际文件为准；后续接口变更请先修改 `docs/api.md` 再变更代码。
