# 11月25日 工作日志 - 史雅萱（后端与工程化 / 队长）

## 今日完成

1. **Dify 接入与解析后端切换**：新增 `app/adapters/dify.py`（李语琛 `agent.py` 的生产化封装：
   `/workflows/run` blocking 调用、`<think>` 清洗、```json 代码块剥离、数组 / 对象双兼容）。
   `LLM_PROVIDER=openai|dify` 一行切换，两条路径共用同一套槽位归一化；
   工作流出数组时**自动取首条**（验收口径），选 `dify` 却漏配 Key 时自动回退 `openai`，现场不会因此启动失败。

2. **`/api/v1/alerts` 主动提醒接口**（`app/routers/alerts.py`）
   - `GET /alerts`：读 `notifications` 表，拉取时事件驱动补扫一次；`level=warning|danger` 决定横幅橙 / 红，
     `data` 同时给「分」与「元」两套金额，前端不做换算；支持 `refresh=false` 纯读库（轮询用）。
   - `POST /alerts/{id}/read`、`POST /alerts/read-all`：横幅关闭。
   - 同时修了 `dao.scan_and_notify` 的**去重口径**：原来每扫一次就删未读再重写，导致用户点「关闭」后
     下次轮询横幅又冒回来。改为按 `(type, category, month)` 原地刷新、保留 `is_read`，
     条件消失的未读才清掉，已读历史保留。`scripts/selfcheck.py` 与 `tests/test_alerts_api.py` 都加了回归断言。

3. **`/api/v1/voice` 语音录入接口**（`app/routers/voice.py` + `app/adapters/asr.py`）
   - `multipart` 收音频（顺手补了 `python-multipart` 依赖，缺它 FastAPI 注册路由时就 RuntimeError）；
   - 三种转写引擎：`auto`（云端 OpenAI 兼容 `/audio/transcriptions`）/ `agent`（调李语琛的
     `speech_to_text(audio_path)`）/ `mock`（离线演示，响应里 `asr_engine=mock` 如实标注）；
   - 转写后复用文本解析出草稿，前端拿到的结构与 `/records/parse` 完全同构；
   - 未配置 / 云端失败 / 没听清 → 统一 `2003` + 中文可读文案，提示「改用文本输入」，
     **文本记账闭环永不受影响**；`GET /voice/status` 让前端提前决定是否禁用录音按钮。
   - 体积护栏 `MAX_UPLOAD_MB`（默认 10MB）。

4. **`/records/ocr` 从占位升级为真实多笔拆单**（`app/adapters/receipt.py`）
   视觉模型或 Dify 多模态 → `drafts[]`，每笔一张确认卡；识别不到金额的行（合计 / 优惠 / 找零）自动丢弃；
   失败时把 `raw_text` 带回，前端可引导用户复制到文本框继续记账。`local` 模式（不打包本地 OCR 模型）
   明确返回 2002，不再假装可用。

5. **CORS**（`app/main.py`）：`CORS_ORIGINS` 可配，默认 `*`；星号与 Cookie 凭证互斥，已自动降级。

6. **公共草稿层** `app/services/draft.py`：把「解析 → 草稿结构（反问文案 / 缺失字段 / draft_id）→ 确认入库
   → 入库后扫提醒」收在一处，text / ocr / voice 三条链路共用，避免三份实现慢慢跑偏。
   `POST /records` 响应补了 `unread_alerts`，聊天页确认成功后可直接点亮横幅。

7. **工程化**
   - `requirements.txt` 补 `python-multipart`；`docker-compose.yml` 转发第二周全部环境变量
     （LLM_PROVIDER / DIFY_* / ASR_* / VISION_* / CORS_ORIGINS / MAX_UPLOAD_MB）；
   - 修 `db/dao.connect` 的 `check_same_thread`：`async def` 路由里 `Depends(get_db)` 的连接由线程池创建、
     却可能在事件循环线程使用，`/voice` 的 auto_commit 直接踩到 `SQLite objects created in a thread...`；
   - 测试：新增 `tests/conftest.py`（临时库隔离，绝不碰 `data/finance.db`）+ 4 个测试文件，
     `pytest tests -q` **132 passed**；`scripts/selfcheck.py` 7 项全过；`scripts/smoke_api.py` 覆盖新接口。

## 与队友的衔接（群里同步）

- **林丹苗（前端）**：契约见 `docs/api.md` §11（语音）/ §12（提醒）。要点：① `/voice` 返回的 `fields` 与
  `/records/parse` 同构，确认卡可直接复用；② `GET /voice/status` 的 `available=false` 时禁用录音按钮；
  ③ 横幅按 `level` 选色、关闭调 `POST /alerts/{id}/read`；④ 入库响应带 `unread_alerts`，可即时点亮横幅。
- **李语琛（AI）**：`agent.py` 的能力已生产化到 `app/adapters/dify.py`（保留你的正则清洗与 `<think>` 剥离逻辑）；
  `ASR_PROVIDER=agent` 时后端会 import `agent.speech_to_text(audio_path)`，约定**入参是音频文件路径、返回字符串**，
  交付时保持这个签名即可直接对接。声音识别请务必不要引入本地模型（镜像体积红线）。
- **蔡适伶（数据）**：`scan_and_notify` 的返回值多了 `inserted` / `updated` 两个键（`budget` / `anomaly` / `total`
  语义不变），去重键是 `(type, category, month)`，`data` 里新增 `month` 字段。`mark_notification_read` 等接口未动。
- **江为（测试）**：新增用例可直接跑 `pytest tests -q`；语音无 Key 环境用 `ASR_PROVIDER=mock` 演示，
  答辩时如实说明；`scripts/smoke_api.py` 已加 `/alerts`、`/voice/status` 两项冒烟。

## 待办 / 风险

- 本机 Docker 守护进程未启动，`docker compose up --build` **未能在今日复验**（配置已按第二周变量更新，
  需在装有 Docker Desktop 的机器上跑一次确认）；接口已用 `uvicorn` 真实 HTTP + TestClient 双路径验证。
- 云端 ASR / 视觉模型都未在此环境联调（无 Key），链路用 `mock` + monkeypatch 覆盖，需在配好 Key 的机器上实测一次。
