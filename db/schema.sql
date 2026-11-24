-- 个人记账助手 · 数据库结构（对齐《项目方案设计文档》v1.1 §4）
-- 与队长 DDL 的差异（数据负责人决策，详见 docs/db-design.md）：
--   1. amount REAL  →  amount_cents INTEGER（存「分」，避免浮点误差）
--   2. budgets.category 用空串 '' 表示总预算（等价 NULL 语义，保证 UNIQUE 生效）
-- 时间统一用 TEXT（YYYY-MM-DD HH:MM:SS），字符串比较即时间比较。

PRAGMA foreign_keys = ON;

-- 消费记录表（核心表）
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'demo_user',
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),  -- 金额，单位「分」
    category    TEXT    NOT NULL,                            -- 类别名（8 类之一）
    merchant    TEXT,                                        -- 商户
    occurred_at TEXT    NOT NULL,                            -- 消费时间（≠ 记账时间）
    source      TEXT    NOT NULL DEFAULT 'text' CHECK (source IN ('text','ocr','voice','manual','demo')),
    raw_text    TEXT,                                        -- 用户原始输入 / OCR 原文
    note        TEXT,
    confirmed   INTEGER NOT NULL DEFAULT 0,                  -- 0 草稿 1 已确认
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_records_time ON records(user_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_records_cat  ON records(user_id, category);

-- 类别表（8 类，keywords 供规则分类兜底）
CREATE TABLE IF NOT EXISTS categories (
    name     TEXT PRIMARY KEY,
    keywords TEXT
);

-- 预算表（category 为空串 '' 表示总预算；等价于队长的 NULL 语义）
CREATE TABLE IF NOT EXISTS budgets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'demo_user',
    category    TEXT    NOT NULL DEFAULT '',
    month       TEXT    NOT NULL,                             -- 'YYYY-MM'
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    UNIQUE(user_id, category, month)
);

-- 会话表（解析上下文，供澄清反问使用）
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    context    TEXT,                                          -- JSON：待补全的草稿槽位
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 主动提醒表（预算警戒 / 异常巡检），第二周新增
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'demo_user',
    type        TEXT    NOT NULL CHECK (type IN ('budget_warning', 'budget_over', 'anomaly')),
    category    TEXT,                                         -- 关联分类；总额预算为 NULL
    level       TEXT    NOT NULL CHECK (level IN ('warning', 'danger')),
    title       TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    data        TEXT,                                         -- JSON 附加数据（used_ratio、amount 等）
    is_read     INTEGER NOT NULL DEFAULT 0,                   -- 0 未读 1 已读
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at);
