"""
触达调度器 — 计划 §4.4。

流程：读 EspoCRM → AI 话术 → 分派各渠道 → 写回 OutreachRecord。
"""

import logging
import os
import time as _time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode
import requests

from .channels import (
    ChannelAdapter, SendResult,
    WAHAChannel, EmailChannel, LinkedInChannel, SocialDMChannel,
)
from ..config import ESPOCRM_URL, ESPOCRM_API_KEY, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_FLASH_MODEL

logger = logging.getLogger("outreach")

DAILY_LIMIT = int(os.getenv("OUTREACH_DAILY_LIMIT", "20"))
MIN_SCORE = int(os.getenv("OUTREACH_MIN_SCORE", "40"))


class OutreachDispatcher:
    """触达统一调度器。"""

    def __init__(self):
        self._espocrm = f"{ESPOCRM_URL}/api/v1"
        self._esh = {"X-Api-Key": ESPOCRM_API_KEY, "Content-Type": "application/json"}
        self._channels: list[ChannelAdapter] = [
            WAHAChannel(),
            EmailChannel(),
            LinkedInChannel(),
            SocialDMChannel("Instagram"),
            SocialDMChannel("Facebook"),
            SocialDMChannel("X"),
            SocialDMChannel("TikTok"),
        ]
        self._counts: dict[str, int] = {}
        self._today = datetime.now().strftime("%Y-%m-%d")

    def _reset_daily(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._today:
            self._counts = {}
            self._today = today

    def _api(self, method: str, path: str, data: dict = None) -> Optional[dict]:
        url = f"{self._espocrm}/{path}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=self._esh, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=self._esh, json=data, timeout=10)
            else:
                return None
            return resp.json() if resp.status_code in (200, 201) else None
        except Exception as e:
            logger.error(f"[Outreach] API error: {e}")
            return None

    def get_leads(self, platform: str, limit: int = 5) -> list[dict]:
        """从 EspoCRM 获取某平台待触达线索。"""
        if platform == "WhatsApp":
            field = "cWhatsapp"
        elif platform == "Email":
            field = "emailAddress"
        else:
            return []

        qs = urlencode({"where[0][type]": "isNotNull", "where[0][attribute]": field,
                        "maxSize": "50", "sortBy": "createdAt", "desc": "true"})
        result = self._api("GET", f"Lead?{qs}")
        logger.info(f"[Outreach] query: {field} -> {result.get('total', 'API-err') if result else 'NONE'} leads")
        if not result:
            return []
        leads = result.get("list", [])
        logger.info(f"[Outreach] raw count: {len(leads)}, scores: {[l.get('cLeadScore','?') for l in leads[:5]]}")
        leads = [l for l in leads if int(l.get("cLeadScore") or 0) >= MIN_SCORE]
        logger.info(f"[Outreach] filtered: {len(leads)} leads >= {MIN_SCORE}")
        return leads[:limit]

    def compose_message(self, lead: dict, platform: str) -> str:
        """AI 话术引擎。"""
        company = lead.get("name", lead.get("firstName", "there"))
        country = lead.get("cLeadCountry", lead.get("addressCountry", ""))
        desc = (lead.get("description") or lead.get("cDeepReport") or "")[:200]
        keywords = lead.get("cSourceKeywords", "")

        prompt = f"""Write a short outreach message for DZATVAPE (professional vape/cannabis device ODM/OEM factory in China, 10+ years).

Target: {company}
Country: {country}
Product interest: {keywords}
Background: {desc}

Platform: {platform}
Rules: 2-3 sentences, natural and human-sounding, no spammy tone. Include company name '{company}'. Output ONLY the message."""

        try:
            resp = requests.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": DEEPSEEK_FLASH_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.7, "max_tokens": 250},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

        company = lead.get("name", lead.get("firstName", "there"))
        country = lead.get("cLeadCountry", lead.get("addressCountry", ""))
        if platform == "Email":
            return f"Dear {company},\n\nI'm reaching out from DZATVAPE, a professional ODM/OEM manufacturer of e-cigarettes and cannabis devices with 10+ years of experience.\n\nWe offer fast R&D (45-day cycle), ISO/GMP certified quality, and flexible MOQ starting at 5,000 units. I'd love to explore how we can support {company}'s product needs in {country}.\n\nWould you be open to a brief chat?\n\nBest regards,\nDZAT TEAM"
        return f"Hi {company}! DZATVAPE here — premium vape/cannabis device ODM/OEM since 2013. Fast R&D, flexible MOQ. Interested in custom products? Let's talk! 📱"

    def dispatch(self, platform: str, limit: int = 5) -> list[SendResult]:
        """执行单平台触达。"""
        self._reset_daily()
        if self._counts.get(platform, 0) >= DAILY_LIMIT:
            logger.info(f"[Outreach] {platform} daily limit reached ({DAILY_LIMIT})")
            return []

        channel = next((ch for ch in self._channels if ch.platform_name == platform), None)
        if not channel:
            return []

        leads = self.get_leads(platform, limit)
        if not leads:
            return []

        results = []
        for lead in leads:
            if self._counts.get(platform, 0) >= DAILY_LIMIT:
                break
            if not channel.can_send_to(lead):
                continue

            lead_id = lead.get("id", "")
            msg = self.compose_message(lead, platform)
            result = channel.send(lead, msg)
            result.lead_id = lead_id

            # 回写 EspoCRM
            status = "已发送" if result.success else "发送失败"
            self._api("POST", "OutreachRecord", {
                "cOutreachPlatform": platform,
                "cOutreachStatus": status,
                "cOutreachMessage": msg[:200],
                "cOutreachLeadId": lead_id,
            })

            if result.success:
                self._counts[platform] = self._counts.get(platform, 0) + 1

            results.append(result)
            logger.info(f"[Outreach] {platform} → {result.target[:30]}: {'OK' if result.success else result.error}")
            _time.sleep(2)

        return results

    def run_all(self) -> dict[str, list[SendResult]]:
        """所有平台各执行一轮。"""
        all_results = {}
        for ch in self._channels:
            results = self.dispatch(ch.platform_name)
            if results:
                all_results[ch.platform_name] = results
        return all_results
