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
│   ├── main.py             # 应用装配：生命周期建库、CORS、全局异常处理、路由注册
│   ├── core/               # 基础设施：配置、响应包装、数据库连接
│   ├── adapters/           # 外部能力接缝：parser（解析）/ dify（工作流）/ asr（语音）/ receipt（小票）
│   ├── services/           # 业务编排：draft（解析→草稿→入库，三条链路共用）
│   └── routers/            # HTTP 路由：health / records / ocr / voice / alerts / query / stats / budgets / meta / demo
├── db/                     # 数据层：建表 SQL + DAO
├── logic/                  # 规则层：金额换算、分类词典、统计、预算、异常巡检、提醒文案（纯函数）
├── frontend/               # Gradio 前端（api 客户端 / ui 组件 / Tab）
├── scripts/                # 演示数据导入、自检、接口冒烟、ASR 评测、提醒造数、录屏分镜生成
├── tests/                  # pytest 用例（数据层、规则层、解析、接口、CORS、语音/OCR 降级）
├── docs/                   # 接口契约、数据库设计、Prompt 说明、进度与工作日志
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

### 前端页面预览

前端共 5 个 Tab，启动后访问 http://localhost:7860/ 即可切换：

```text
┌────────────┬─────────────────────────────────────────────┐
│ 功能导航    │ 记账小助手 · 说一句话记账，问一句话查账       │
├────────────┼─────────────────────────────────────────────┤
│ 记账对话    │ Tab1: 聊天流 + 胶囊输入栏（加号菜单）        │
│            │       + 草稿确认卡 + 查账表格               │
├────────────┼─────────────────────────────────────────────┤
│ 明细管理    │ Tab2: 日期/类别筛选 + 分页明细 + 修改/删除   │
├────────────┼─────────────────────────────────────────────┤
│ 统计图表    │ Tab3: 月度指标卡 + 类别饼图 / 每日趋势折线   │
├────────────┼─────────────────────────────────────────────┤
│ 预算中心    │ Tab4: 预算设定 + 已设清单 + 三态进度预警     │
├────────────┼─────────────────────────────────────────────┤
│ 演示入口    │ Tab5: 一键灌入/清空演示数据 + 后端自检       │
└────────────┴─────────────────────────────────────────────┘
```

| Tab | 主要接口 | 说明 |
|---|---|---|
| 记账对话 | `/records/parse`、`/query`、`/records/ocr`、`/records` | 记账语句出草稿；问句只展示后端 `answer_text`/`table`；小票支持多笔勾选 |
| 明细管理 | `GET/PUT/DELETE /records` | 分页、筛选、修正、二次确认删除 |
| 统计图表 | `/stats/summary`、`/stats/by-category`、`/stats/trend` | 图表数据全部来自后端聚合 |
| 预算中心 | `POST/GET /budgets`、`/budgets/alerts`、`/categories` | 类别/总额双维度，80% 预警、100% 超支 |
| 演示入口 | `/health`、`/demo/load`、`/demo/reset` | 无 Key 评审环境一键体验全链路 |
| 语音 / 全局横幅（第二周） | `POST /voice`、`GET /voice/status`、`GET /alerts`、`POST /alerts/{id}/read` | 录音转文字出草稿；顶部红 / 橙提醒横幅，可单条或全部关闭 |

> 页面截图：当前开发环境没有浏览器自动化工具，无法生成真实截图；请在可浏览环境打开前端后，将各 Tab 截图保存到 `docs/screenshots/` 并在本表补充引用。

> **数据持久化**：`docker-compose.yml` 用**目录挂载**（宿主 `./data` ⇄ 容器 `/app/data`），数据库文件为容器内 `/app/data/finance.db`，容器重建、镜像升级都不丢数据。
> 由于是绑定挂载，`docker compose down -v` **不会**删除数据；要清空数据请删除宿主 `data/finance.db`，或在界面「演示数据」页点击「清空演示数据」（等价于调用 `POST /demo/reset`）。
> 端口：后端 `8000`、前端 `7860`，均由 compose 显式声明。
>
> 已实测（Windows 11 + Docker Desktop 29.9.3）：`docker compose up --build` 后 backend 状态 `healthy`、前端 `7860` 返回 200、`/api/v1/stats/summary` 等接口返回真实数据；容器重建后 `./data/finance.db` 中的流水与预算仍在。
> pip 默认走清华镜像（`Dockerfile` 的 `PIP_INDEX_URL` 构建参数），国内网络下构建约 45 分钟（其中 apt 源 12 分钟）；网络较好时数分钟即可。

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
| LLM_PROVIDER | openai | 解析后端开关：`openai` 直连模型 / `dify` 走 Dify 工作流（第二周验收项「LLM 调用可切 Dify」） |
| LLM_API_KEY | 空 | 大模型 API 密钥（OpenAI 兼容接口）；留空则解析走规则兜底，功能不受影响 |
| LLM_BASE_URL | https://api.deepseek.com/v1 | API 地址 |
| LLM_MODEL | deepseek-chat | 模型名 |
| LLM_TIMEOUT | 30 | 单次模型调用超时（秒） |
| DIFY_API_KEY | 空 | Dify 工作流密钥（`app-` 开头）；`LLM_PROVIDER=dify` 时必填，缺失会自动回退 openai |
| DIFY_BASE_URL | https://api.dify.ai/v1 | Dify API 地址（私有部署改这里） |
| DIFY_INPUT_KEY | user_input | 工作流开始节点接收用户输入的变量名 |
| ASR_PROVIDER | auto | `auto` 云端转写 / `agent` 调李语琛的 `speech_to_text` / `mock` 离线演示；**镜像内不含本地语音模型** |
| ASR_API_KEY | 空（回退 LLM_API_KEY） | 云端语音识别密钥；留空时 `/voice` 明确返回 2003 并提示改用文本输入 |
| ASR_BASE_URL / ASR_MODEL | https://open.bigmodel.cn/api/paas/v4 / glm-asr | OpenAI 兼容的 `/audio/transcriptions` 端点与模型 |
| ASR_MOCK_TEXT | 昨天打车 32 块 | `ASR_PROVIDER=mock` 时固定返回的演示转写文本 |
| OCR_PROVIDER | local | `api` 走视觉模型（支持多笔）/ `dify` 走多模态工作流 / `local` 不打包本地模型（返回 2002） |
| VISION_API_KEY / VISION_BASE_URL / VISION_MODEL | 空 / 同 LLM_BASE_URL / glm-4v-flash | 视觉模型凭据；解析模型不一定能读图，所以单独一组 |
| CORS_ORIGINS | * | 逗号分隔的允许来源；`*` 方便评审机器直连 8000 |
| MAX_UPLOAD_MB | 10 | 语音与图片上传体积上限 |
| DB_PATH | data/finance.db | SQLite 路径；容器内被 compose 覆盖为 `/app/data/finance.db` |
| DEFAULT_USER_ID | demo_user | 单用户演示版固定用户 ID |
| API_BASE_URL | http://localhost:8000/api/v1 | 前端请求地址；容器内为 `http://backend:8000/api/v1` |
| FRONTEND_HOST / FRONTEND_PORT | 0.0.0.0 / 7860 | 前端监听地址与端口 |
| MOCK_FALLBACK | 0 | `1` 时前端在接口不可用时降级到本地假数据；**默认关闭**，评审须看到数据库真实数据 |

> 真实密钥不得提交到仓库（`.env` 已在 `.gitignore` 中）。

## 7. 当前进度（Current Progress）

### 7.1 第二周新增（2026-11-25）

| 能力 | 状态 | 说明 |
|---|---|---|
| Dify 接入开关 | 已实现 | `LLM_PROVIDER=dify` 走李语琛的 Dify 工作流，`openai` 直连模型；输出是数组时自动取首条，对象 / 数组双兼容 |
| `/alerts` 主动提醒 | 已实现 | 读 `notifications` 表，`level` 决定横幅红/橙；支持单条已读、全部已读；同月同类提醒去重，关闭后不会被轮询刷回 |
| 入库后事件驱动扫描 | 已实现 | `POST /records` 落库后自动扫预算警戒 + 异常巡检，并把 `unread_alerts` 一并返回 |
| `/voice` 语音录入 | 已实现 | 音频 → 云端 ASR → 复用文本解析 → 草稿；`/voice/status` 供前端决定是否禁用录音按钮 |
| `/records/ocr` 多笔拆单 | 已实现 | 视觉模型 / Dify 多模态 → `drafts[]`，每笔一张确认卡；识别不到金额的行自动丢弃 |
| CORS 跨域 | 已实现 | `CORS_ORIGINS` 可配，默认 `*` 方便评审机器直连 |
| 三条链路共用草稿层 | 已实现 | `app/services/draft.py` 统一「解析 → 草稿 → 入库」，text / ocr / voice 结构完全一致 |

### 7.2 第一周已完成

| 能力 | 状态 | 说明 |
|---|---|---|
| 健康检查 / 统一响应包装 | 已实现 | `/api/v1/health` 返回标准 `{code, message, data}` |
| 启动自动建表 | 已实现 | 首次启动自动建 5 张表（含 `notifications`）并初始化分类字典 |
| 自然语言记账 `/records/parse` | 已实现 | 有 Key 走 LLM / Dify，无 Key 走规则兜底；缺金额/时间返回 `clarify_question` |
| 记账入库 / 明细增删改查 | 已实现 | `/records` 五个接口全部打通，金额按「分」存储、「元」返回 |
| 消费自动分类与统计 | 已实现 | `/stats/summary`、`/stats/by-category`、`/stats/trend` 全部基于真实入库数据 |
| 自然语言查账 `/query` | 已实现 | 槽位抽取（时间/类别/聚合）→ 数据库聚合 → 模板生成回答，模型不参与算数 |
| 预算与超支提醒 | 已实现 | `/budgets` 三个接口，0.8 预警 / 1.0 超支由后端判定 |
| 演示数据一键灌入 / 清空 | 已实现 | `/demo/load`（幂等）、`/demo/reset` |
| 前端 Gradio 界面 | 已实现 | 五个 Tab 全部对接真实接口，`MOCK_FALLBACK` 默认关闭 |

## 8. 功能清单与验证方式（Feature Checklist & Verification）

评审按下面顺序在界面上点一遍，即可覆盖必做清单的全部四项（括号内为对应的接口）。

### 8.1 准备演示数据

进入「演示数据」Tab，点「灌入演示数据」（`POST /demo/load`），预期提示 `60 条流水 / 2 个月份`（来自根目录 `demo_bills.csv`），并自动布置 4 条当月预算（总额 4000、餐饮 1200、交通 500、娱乐 100）。重复点击不会重复灌入（幂等）。

### 8.2 功能 1：自然语言记账 + 入库

在「记账」Tab 输入 `昨天打车 32 块`（`POST /records/parse`）：

* 预期返回 `fields.amount = 32`、`category = 交通`、`occurred_at` 为昨天、`confidence` 0.62~0.9；
* 点「确认入库」（`POST /records`），刷新「明细」Tab 能看到这条记录；
* 若输入 `花了点钱`，不会瞎猜金额，而是返回 `clarify_question = 请输入金额`。

### 8.3 功能 2：自动分类与统计

「明细」Tab 顶部展示当月总额与笔数，「统计」Tab 展示三类视图（`GET /stats/summary`、`/stats/by-category`、`/stats/trend`）。
以示例账单为准，2026-11 预期为：总额 `¥2410.40`、9 笔、日均 `¥133.91`；分类占比中「居住」`¥2000.00` 占 `83%`。

### 8.4 功能 3：自然语言查账

「记账」Tab 下方问句框（或「统计」Tab 的提问入口，`POST /query`）。示例与预期回答（时间以 2026-11 为「本月」基准）：

| 提问 | 预期 `answer_text` |
|---|---|
| 我上个月吃饭花了多少？ | `10 月，「餐饮」共支出 ¥160.50，共 2 笔。` |
| 这个月哪类花得最多？ | `11 月，花得最多的是「居住」，共 ¥2,000.00（83%），1 笔。` |
| 最近 7 天一共花了多少钱 | `最近 7 天，共支出 ¥174.00，共 2 笔。` |
| 最近 30 天支出趋势 | 返回逐日 `table`，最高的一天为 `2026-11-01`（`¥2,000.00`） |

回答中的数字全部由 SQL 聚合得出；`slots` 会回显解析出的时间区间与类别，便于核对「有没有真的解析」。

### 8.5 功能 4：预算与超支提醒

「预算」Tab 设置「娱乐」类 100 元（`POST /budgets`），进度条应立刻变红并显示 `113%`（已用 `¥113.00`、`status = over`）；设总额 4000 元则为 `normal`（`60%`）。预警阈值 80%（`warning`），判断在后端完成。

### 8.6 功能 5：语音输入与主动提醒（第二周）

**语音记账**（`POST /voice`，前端录音按钮）：

* 浏览器允许麦克风后说「昨天打车 32 块」，返回 `transcript` + 与文本链路同构的草稿，点确认入库；
* 若未配置 `ASR_API_KEY`，接口返回 `2003` 并提示「请改用文本输入」——**文本输入始终可用**，这是硬性降级要求；
* 没有麦克风的评标环境：设置 `ASR_PROVIDER=mock`，录音后固定返回 `ASR_MOCK_TEXT`，可完整演示链路；
  响应里 `asr_engine=mock` 会如实标注，不会把演示结果冒充成真实识别。

**主动提醒横幅**（`GET /alerts`）：

1. 在「预算」Tab 给「娱乐」设 100 元，再记一笔 90 元娱乐 → 横幅为**橙色**（`level=warning`，已用 90%）；
2. 再记一笔 30 元娱乐（累计 120 元）→ 横幅变**红色**（`level=danger`，已超支）；
3. 点横幅上的「×」（`POST /alerts/{id}/read`）→ 横幅消失；刷新页面**不会**再冒出来（同月同类去重）；
4. 点「全部关闭」（`POST /alerts/read-all`）→ 一次清空。

> 已修复的端到端 Bug：前端曾把 `/voice` 的 `transcript` 误读成 `text`，录音识别成功却永远回填空串；
> 横幅曾直接读实时预算进度，点关闭后刷新会复活。现在横幅以 `/alerts` 的持久化已读状态为准，
> 关闭会调用 `POST /alerts/read-all`。修正 / 删除撑爆预算的记录后也会立即重扫并撤掉横幅。

### 8.7 自动化测试

```bash
pytest tests -q            # 数据层 / 规则层 / 解析 / 接口 / CORS / 语音与 OCR 降级 / 端到端回归 / ASR 评测工具（156 passed）

python scripts/selfcheck.py   # 不装 pytest 也能跑的核心逻辑自检（7 项）

python scripts/smoke_api.py   # 需先启动后端：按前端客户端的调用方式跑一遍全部接口，
                              # 并用前端渲染函数消费返回字段，验证前后端无字段错位

docker compose exec backend python -m pytest tests -q   # 镜像内已包含 tests/，容器内同样可自检
```

### 8.8 全模态与提醒专项测试

**语音准确率实测**（不同麦克风 / 环境噪音）：

```bash
python scripts/asr_benchmark.py self-test            # 无麦克风自检：CER/分组/报告链路
# 1) 把原始录音按 <设备>__<噪声>__<phrase01|02|03>.m4a 命名，一键转 WAV 并生成 manifest：
python scripts/asr_sample_helper.py --input "C:/path/to/raw_recordings"
# 2) 也可手工填 data/asr_samples/manifest.template.csv；若只有安静环境录音，可派生噪声仿真样本：
python scripts/asr_benchmark.py derive --input data/asr_samples/manifest.template.csv
# 3) 配好 ASR_API_KEY 并启动后端后实测；结果写入 docs/asr-benchmark-report.md
python scripts/asr_benchmark.py run --manifest data/asr_samples/manifest.csv --backend api \
  --base-url http://127.0.0.1:8000/api/v1 --report docs/asr-benchmark-report.md
```

云端协议按供应商三选一（`.env` 里配，容器由 compose 注入）：

```ini
# 智谱 GLM：OpenAI 标准 /audio/transcriptions
ASR_PROVIDER=auto
ASR_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ASR_MODEL=glm-asr
ASR_PROTOCOL=openai

# 阿里云百炼 DashScope：没有 /audio/transcriptions，需走 chat/completions + input_audio
ASR_PROVIDER=auto
ASR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ASR_MODEL=qwen3-asr-flash
ASR_PROTOCOL=chat

# 阿里云百炼全模态模型（当前默认，有免费额度）：除 audio 外还要给文字指令、
# 显式关掉深度思考；模型不认 asr_options，改用指令要求金额写阿拉伯数字。
ASR_PROVIDER=auto
ASR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ASR_MODEL=qwen3.8-omni-flash
ASR_PROTOCOL=omni
```

> `qwen3.8-omni-flash` 是**全模态模型**（文本/图片/音频/视频输入），语音转写是能力之一，
> 不是专用 ASR；实测 6 条真实样本（笔记本麦克风 × 安静/风扇噪音）**CER=0 / 准确率 100%**。
> `qwen-mt-uni` 是**翻译模型**（需 `target_lang`，音频翻译为音频），**不能**用于语音识别。

换配置后 `docker compose up -d --build --force-recreate backend`（改了源码必须 rebuild，只 recreate 会跑旧镜像）。
`chat` 协议下 ITN 默认开启，把「三十二」规范化成「32」；`omni` 协议下由文字指令达到同样效果。

报告按「设备 × 噪声条件」给出字符准确率 `1 - CER`、完全匹配率与失败数。
若样本含 `engine=mock`，报告标题与开头会自动标注「不可作为真实准确率交付」，防止误交。
`derive` 只做增益/噪声仿真，不能替代真实麦克风录音；`mock` 引擎的数字只用于验证工具链，
答辩时请如实说明。输入需为 16-bit 单声道 WAV（`ffmpeg -i in.webm -ac 1 -ar 16000 -c:a pcm_s16le out.wav`）。

**预算爆表数据 + 横幅验证**：

```bash
python scripts/load_alert_fixture.py                  # 临时库跑通，绝不碰 data/finance.db
# 或灌入正在运行的后端用于现场演示：
python scripts/load_alert_fixture.py --mode api --base-url http://127.0.0.1:8000/api/v1
```

数据文件 `data/alert_fixture.json` 会同时制造：餐饮 90/100（橙色 warning）、
娱乐 130/100（红色 over）、交通 500/总预算 2000（正常）。脚本会断言 `/alerts` 同时返回
橙、红两条提醒，并把真实横幅 HTML 写入 `docs/alert-banner-sample.html`。

### 8.9 答辩演示录屏物料

**真实界面录屏**（推荐用作答辩主视频）：

```bash
# 前置：docker compose up -d --build，浏览器打开 http://localhost:7860 并置于前台
python scripts/record_gui_demo.py --out docs/demo-recording.mp4 --seconds 50
```

脚本用 mss 抓屏 + ffmpeg 编码，按「片头横幅 → 对话追问 → 草稿生成 → 统计图表」四幕
自动点击真实 Gradio 界面，产出 `docs/demo-recording.mp4`（约 68 秒、1280×720）。
依赖 `mss / pyautogui / opencv-python / imageio-ffmpeg`。

**分镜预演动画**（备用/先讲故事线）：

```bash
python scripts/demo_record.py            # 生成 docs/demo-storyboard.mp4 + 分镜说明
```

动画底层数据全部来自真实接口链路，但不是 Gradio 界面录屏；
真实录屏步骤、旁白文案与镜头时长见 `docs/答辩演示录屏脚本.md`。

**横幅弹不出来时（数据已读/已保存）**：横幅读的是 `/alerts` 持久化提醒，点过「✕」后
`is_read=1` 会一直保留，普通刷新/重扫不会复活（这是正确行为）。答辩要反复演示弹出时，
跑 `python scripts/replay_alert_banner.py` 或点页面顶部「🔄 重播横幅」按钮，一键重置为未读；
脚本会在库为空时自动灌入餐饮 90%/娱乐 130% 触发数据。详见 `docs/答辩演示录屏脚本.md` §2.5。

## 9. 团队分工（Team Division）

| 成员 | 负责内容 |
|---|---|
| 史雅萱 | 后端与工程化（队长）：FastAPI 接口开发、Docker 容器化、接口契约制定、Git 合并 |
| 李语琛 | AI 核心：Dify 工作流搭建、Prompt 设计、多模态图片识别、结构化解析 |
| 蔡适伶 | 数据与规则：SQLite 建表、分类词典维护、统计 SQL 编写、预算预警逻辑 |
| 林丹苗 | 前端：Gradio 界面开发、图表可视化、前后端接口联调 |
| 江为 | 测试与交付：示例账单数据准备、测试用例编写、README 维护、答辩 PPT 与演示视频 |

> 启动命令以本文与仓库实际文件为准；后续接口变更请先修改 `docs/api.md` 再变更代码。
