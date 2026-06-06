"""
触达渠道 — 计划 §4.4 统一 Channel 接口。

ChannelAdapter        ← 抽象基类
├── WAHAChannel       ← WhatsApp (WAHA REST API)
├── EmailChannel      ← SendGrid API (fallback SMTP)
├── LinkedInChannel   ← Playwright (待 Chrome Pool)
└── SocialDMChannel   ← IG/FB/X/TikTok 统一 (待 Chrome Pool)
"""

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any, Optional
import requests

from ..config import WAHA_URL, WAHA_API_KEY

logger = logging.getLogger("outreach")


@dataclass
class SendResult:
    success: bool
    platform: str
    lead_id: str = ""
    target: str = ""
    message: str = ""
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── 统一接口 ────────────────────────────────────

class ChannelAdapter(ABC):
    """所有触达渠道的统一接口。"""

    platform_name: str = ""

    @abstractmethod
    def send(self, lead: dict, message: str) -> SendResult:
        """发送触达消息。子类实现。"""
        ...

    @abstractmethod
    def can_send_to(self, lead: dict) -> bool:
        """检查是否可向此 Lead 发送。"""
        ...


# ── WhatsApp ─────────────────────────────────────

class WAHAChannel(ChannelAdapter):
    """WhatsApp 触达（WAHA REST API）。"""

    platform_name = "WhatsApp"

    def __init__(self):
        self._url = f"{WAHA_URL}/api"
        self._headers = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}

    def can_send_to(self, lead: dict) -> bool:
        phone = (lead.get("phoneNumber") or "").strip()
        return bool(phone and len(phone) >= 7)

    def send(self, lead: dict, message: str) -> SendResult:
        phone = (lead.get("cWhatsapp") or lead.get("phoneNumber") or "").strip()
        chat_id = phone.lstrip("+")
        if "@" not in chat_id:
            digits = "".join(c for c in chat_id if c.isdigit())
            chat_id = f"{digits}@c.us" if len(digits) <= 13 else f"{digits}@lid"

        try:
            resp = requests.post(
                f"{self._url}/sendText",
                headers=self._headers,
                json={"chatId": chat_id, "text": message, "session": "default"},
                timeout=15,
            )
            ok = resp.status_code in (200, 201)
            return SendResult(
                success=ok, platform="WhatsApp", target=chat_id, message=message,
                error="" if ok else f"HTTP {resp.status_code}",
            )
        except Exception as e:
            return SendResult(success=False, platform="WhatsApp", target=chat_id, message=message, error=str(e))


# ── Email (SendGrid API + SMTP fallback) ────────

class EmailChannel(ChannelAdapter):
    """Email 触达 — 优先 SendGrid API，未配置时用 SMTP。"""

    platform_name = "Email"

    def __init__(self):
        self._sg_key = os.getenv("SENDGRID_API_KEY", "")
        self._smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self._smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self._smtp_user = os.getenv("SMTP_USER", "")
        self._smtp_pass = os.getenv("SMTP_PASSWORD", "")
        self._from = self._smtp_user or os.getenv("SENDGRID_FROM", "dzat@dzatvape.com")

    def can_send_to(self, lead: dict) -> bool:
        return bool((lead.get("emailAddress") or "").strip())

    def send(self, lead: dict, message: str) -> SendResult:
        to_email = lead.get("emailAddress", "").strip()
        company = lead.get("name", lead.get("firstName", "Partner"))
        subject = f"DZATVAPE | Vape ODM/OEM | {company[:30]}"
        body_html = message.replace("\n", "<br>")

        if self._sg_key:
            return self._send_via_sendgrid(to_email, subject, body_html)
        return self._send_via_smtp(to_email, subject, body_html)

    def _send_via_sendgrid(self, to: str, subject: str, body: str) -> SendResult:
        try:
            resp = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {self._sg_key}"},
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": self._from},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": body}],
                },
                timeout=15,
            )
            ok = resp.status_code in (200, 202)
            return SendResult(success=ok, platform="Email", target=to, message=subject,
                              error="" if ok else f"SendGrid {resp.status_code}")
        except Exception as e:
            return SendResult(success=False, platform="Email", target=to, message=subject, error=str(e))

    def _send_via_smtp(self, to: str, subject: str, body: str) -> SendResult:
        if not self._smtp_user or not self._smtp_pass:
            return SendResult(success=False, platform="Email", target=to, message=subject, error="SMTP not configured")
        try:
            msg = MIMEText(body, "html", "utf-8")
            msg["From"] = self._smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=15) as s:
                s.starttls()
                s.login(self._smtp_user, self._smtp_pass)
                s.send_message(msg)
            return SendResult(success=True, platform="Email", target=to, message=subject)
        except Exception as e:
            return SendResult(success=False, platform="Email", target=to, message=subject, error=str(e))


# ── LinkedIn (Playwright — 待 Chrome Pool) ──────

class LinkedInChannel(ChannelAdapter):
    """LinkedIn 触达（Playwright CDP — 待 Chrome Pool 上线）。"""

    platform_name = "LinkedIn"

    def can_send_to(self, lead: dict) -> bool:
        return bool((lead.get("cLinkedin") or "").strip())

    def send(self, lead: dict, message: str) -> SendResult:
        return SendResult(success=False, platform="LinkedIn",
                          target=lead.get("cLinkedin", ""), message=message,
                          error="LinkedIn channel pending Chrome Pool deployment")


# ── 社媒 DM (IG/FB/X/TikTok — 待 Chrome Pool) ──

class SocialDMChannel(ChannelAdapter):
    """社媒 DM 触达 — IG/FB/X/TikTok 统一基类（待 Chrome Pool）。"""

    def __init__(self, platform: str):
        self.platform_name = platform
        self._field_map = {"Instagram": "cInstagram", "Facebook": "cFacebook",
                           "X": "cXHandle", "TikTok": "cTiktok"}

    def can_send_to(self, lead: dict) -> bool:
        field = self._field_map.get(self.platform_name, "")
        return bool((lead.get(field) or "").strip())

    def send(self, lead: dict, message: str) -> SendResult:
        field = self._field_map.get(self.platform_name, "")
        return SendResult(success=False, platform=self.platform_name,
                          target=lead.get(field, ""), message=message,
                          error=f"{self.platform_name} channel pending Chrome Pool deployment")
