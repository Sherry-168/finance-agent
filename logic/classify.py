"""规则分类：基于关键词词典，作为 LLM 分类失败时的兜底。

与 LLM 的边界：LLM 优先输出 category，本模块负责校验它是否落在 8 类之内；
LLM 失败或输出非法类别时，用关键词词典兜底分类；仍匹配不到则落「其他」。
"""
from __future__ import annotations

import json
from pathlib import Path

CATEGORIES_PATH = Path(__file__).resolve().parent.parent / "config" / "categories.json"


def load_keywords() -> dict[str, list[str]]:
    """返回 {类别: [关键词]}。"""
    return json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))


def known_categories() -> list[str]:
    """返回 8 个合法类别名（供 Prompt 枚举约束与前端渲染）。"""
    return list(load_keywords().keys())


def is_valid_category(name: str | None) -> bool:
    return bool(name) and name in load_keywords()


def normalize_category(name: str | None) -> str:
    """把 LLM 给出的类别规范到 8 类之一；非法 / 空则落「其他」。"""
    if is_valid_category(name):
        return name
    return "其他"


def classify(text: str, keywords: dict[str, list[str]] | None = None) -> str:
    """按关键词命中数返回最匹配的类别；无命中返回「其他」。"""
    keywords = keywords or load_keywords()
    text = text or ""
    best, best_score = "其他", 0
    for cat, kws in keywords.items():
        if cat == "其他":
            continue
        score = sum(1 for kw in kws if kw and kw in text)
        if score > best_score:
            best, best_score = cat, score
    return best
