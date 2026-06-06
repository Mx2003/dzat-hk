"""
Chrome Pool 客户端 — Playwright CDP 直连 browserless/chrome。

browserless/chrome 暴露 WebSocket: ws://chrome-pool:3000
Playwright connect_over_cdp 直接连，和 Windows 系统一样的 CDP 协议。
"""

import logging
from playwright.sync_api import sync_playwright, Browser, Page

logger = logging.getLogger("discovery.chrome_pool")

# chrome-pool uses network_mode:host, Gateway accesses via docker host
import os
_HOST = os.environ.get("DOCKER_HOST_IP", "172.17.0.1")
CHROME_WS = f"ws://{_HOST}:3000"

_browser: Browser | None = None
_playwright = None


def get_browser() -> Browser:
    global _browser, _playwright
    if _browser is None or not _browser.is_connected():
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.connect_over_cdp(CHROME_WS)
        logger.info("[Chrome] CDP connected")
    return _browser


def new_page() -> Page:
    return get_browser().contexts[0].new_page()


def fetch_page(url: str, timeout: int = 20) -> str:
    """CDP 浏览器 + 反检测，返回页面 HTML。"""
    from .anti_detection import setup_page_stealth
    page = new_page()
    try:
        setup_page_stealth(page)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        page.wait_for_timeout(3000)
        return page.content()
    except Exception as e:
        logger.warning(f"[Chrome] {url[:50]}: {e}")
        return ""
    finally:
        page.close()


def get_page() -> Page:
    """获取带有反检测 + 代理的 Playwright Page。"""
    from .anti_detection import setup_page_stealth
    browser = get_browser()
    # SOCKS5 代理（hysteria → 127.0.0.1:1080）
    context = browser.new_context(proxy={"server": "socks5://127.0.0.1:1080"})
    page = context.new_page()
    setup_page_stealth(page)
    return page
