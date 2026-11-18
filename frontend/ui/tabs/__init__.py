"""五个功能区：记账对话 / 明细管理 / 统计图表 / 预算中心 / 演示入口。"""

from ui.tabs.budget_tab import build_budget_tab
from ui.tabs.chat_tab import build_chat_tab
from ui.tabs.demo_tab import build_demo_tab
from ui.tabs.records_tab import build_records_tab
from ui.tabs.stats_tab import build_stats_tab

__all__ = [
    "build_chat_tab",
    "build_records_tab",
    "build_stats_tab",
    "build_budget_tab",
    "build_demo_tab",
]
