"""
Gateway 配置 — 从环境变量读取，零硬编码密钥。
所有真实值由 docker-compose.yml 注入。
"""

import os
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


WAHA_URL = _env("WAHA_URL", "http://waha:3001")
WAHA_API_KEY = _env("WAHA_API_KEY")

CHATWOOT_URL = _env("CHATWOOT_URL", "http://chatwoot-rails:3000")
CHATWOOT_API_TOKEN = _env("CHATWOOT_API_TOKEN")
CHATWOOT_ACCOUNT_ID = int(_env("CHATWOOT_ACCOUNT_ID", "3"))
CHATWOOT_INBOX_ID = int(_env("CHATWOOT_INBOX_ID", "1"))

ESPOCRM_URL = _env("ESPOCRM_URL", "http://espocrm")
ESPOCRM_API_KEY = _env("ESPOCRM_API_KEY")

DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = _env("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_FLASH_MODEL = _env("DEEPSEEK_FLASH_MODEL", "deepseek-v4-flash")

WECHAT_WEBHOOK_URL = _env("WECHAT_WEBHOOK_URL")

KNOWLEDGE_DIR = Path(_env("KNOWLEDGE_DIR", "/app/knowledge"))

REDIS_URL = _env("REDIS_URL", "redis://redis:6379/0")
