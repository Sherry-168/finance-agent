"""主题样式：读取 assets/style.css 并以自定义 CSS 注入 Blocks。"""

from pathlib import Path

import gradio as gr

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def load_css() -> str:
    """读取自定义样式，供 gr.Blocks(css=...) 注入。"""
    css_path = _ASSETS_DIR / "style.css"
    if not css_path.exists():
        return ""
    return css_path.read_text(encoding="utf-8")


APP_CSS = load_css()


def app_theme() -> gr.themes.Base:
    """主题色与自定义 CSS 保持一致的浅色主题。"""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.teal,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        radius_size=gr.themes.sizes.radius_lg,
        # 只用系统字体，避免离线 / 内网评审环境加载外链字体失败
        font=[
            "-apple-system", "BlinkMacSystemFont", "SF Pro Text", "PingFang SC",
            "Microsoft YaHei", "Noto Sans SC", "Segoe UI", "sans-serif",
        ],
    )
