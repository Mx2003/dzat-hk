"""
企微 Webhook 通知。

计划 §八：客服转人工通知、服务告警、每日摘要。
"""

import logging
from datetime import datetime
from typing import Optional, Any
import requests

from .config import WECHAT_WEBHOOK_URL, WECHAT_HANDOFF_URL

logger = logging.getLogger("wechat_notify")


class WeChatNotifier:
    """企微机器人通知。"""

    def __init__(self):
        self._url = WECHAT_WEBHOOK_URL
        self._handoff_url = WECHAT_HANDOFF_URL

    def _send_markdown(self, content: str, use_handoff: bool = False) -> bool:
        """发送 Markdown 消息。"""
        url = self._handoff_url if use_handoff else self._url
        if not url:
            logger.warning("[WeChat] Webhook URL not configured")
            return False
        try:
            resp = requests.post(
                url,
                json={"msgtype": "markdown", "markdown": {"content": content}},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[WeChat] error: {e}")
            return False

    def notify_handoff(
        self,
        customer_name: str,
        phone: str = "",
        language: str = "",
        trigger_reason: str = "",
        customer_msgs: list[str] = None,
        conversation_summary: str = "",
    ) -> bool:
        """转人工通知（详细版）。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 优先级
        priority = "NORMAL 🟡"
        if trigger_reason and "明确请求" in trigger_reason:
            priority = "HIGH 🔴"
        if trigger_reason and "3轮" in trigger_reason:
            priority = "NORMAL 🟡"

        lang_display = language or "unknown"

        # 客户消息摘要
        msg_lines = ""
        if customer_msgs:
            for i, m in enumerate(customer_msgs[-3:], 1):
                msg_lines += f"\n> {i}. {m[:60]}"

        # 对话摘要
        conv_text = conversation_summary or "(no history)"

        md = f"""## 🔔 新转人工请求
> 客户: **{customer_name}** `{phone}`
> 语言: {lang_display}
> 优先级: {priority}
> 触发原因: {trigger_reason or "自动转接"}
> 时间: {now}

**客户消息**:{msg_lines if msg_lines else "\n> (no recent messages)"}

**对话摘要**:
{conv_text}

---
> 🤖 DZAT Gateway · 请尽快在 Chatwoot 中处理"""

        return self._send_markdown(md, use_handoff=True)

    def notify_alert(self, title: str, detail: str) -> bool:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return self._send_markdown(f"## ⚠️ {title}\n> 时间: {now}\n> {detail}")

    def notify_daily_summary(self, markdown: str) -> bool:
        return self._send_markdown(markdown)


_notifier: Optional[WeChatNotifier] = None


def get_notifier() -> WeChatNotifier:
    global _notifier
    if _notifier is None:
        _notifier = WeChatNotifier()
    return _notifier
