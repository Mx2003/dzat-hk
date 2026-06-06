"""
EspoCRM REST 客户端 — Lead 查询/创建/更新。

计划 §4.1：Gateway API 作为唯一写入方，通过 EspoCRM REST API 读写。
"""

from typing import Any, Optional
import requests

from .config import ESPOCRM_URL, ESPOCRM_API_KEY


class EspoCRMClient:
    """EspoCRM REST API 封装。"""

    def __init__(self):
        self._base = f"{ESPOCRM_URL}/api/v1"
        self._headers = {
            "X-Api-Key": ESPOCRM_API_KEY,
            "Content-Type": "application/json",
        }

    def _api(self, method: str, path: str, data: Optional[dict] = None) -> Optional[dict]:
        """通用 API 调用。"""
        url = f"{self._base}/{path}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=self._headers, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=self._headers, json=data, timeout=10)
            elif method == "PUT":
                resp = requests.put(url, headers=self._headers, json=data, timeout=10)
            else:
                return None
            if resp.status_code in (200, 201):
                return resp.json()
            return None
        except Exception:
            return None

    # ── Lead CRUD ──────────────────────────────

    def find_lead_by_phone(self, phone: str) -> Optional[dict]:
        """通过电话号码查找已有线索。"""
        digits = "".join(c for c in phone if c.isdigit())[-10:]
        result = self._api("GET", f"Lead?where[0][type]=contains&where[0][attribute]=phoneNumber&where[0][value]={digits}")
        if result and result.get("list"):
            return result["list"][0]
        return None

    def create_lead(self, data: dict[str, Any]) -> Optional[dict]:
        """创建新线索。自定义字段加 c 前缀。"""
        payload = {
            "firstName": data.get("name", "WhatsApp")[:50],
            "lastName": data.get("phone", "Unknown")[:20],
            "phoneNumber": data.get("phone", ""),
            "description": data.get("note", ""),
            "cSourceKeywords": data.get("source", "inbound_whatsapp"),
        }
        return self._api("POST", "Lead", payload)

    def update_lead(self, lead_id: str, data: dict[str, Any]) -> Optional[dict]:
        """更新线索。"""
        return self._api("PUT", f"Lead/{lead_id}", data)

    def create_outreach_record(self, lead_id: str, platform: str, status: str, message: str = "") -> Optional[dict]:
        """创建触达记录。"""
        return self._api("POST", "OutreachRecord", {
            "cOutreachPlatform": platform,
            "cOutreachStatus": status,
            "cOutreachMessage": message,
            "cOutreachLeadId": lead_id,
        })

    # ── Contact ─────────────────────────────────

    def find_contact_by_phone(self, phone: str) -> Optional[dict]:
        """通过电话查找联系人。"""
        digits = "".join(c for c in phone if c.isdigit())[-10:]
        result = self._api("GET", f"Contact?where[0][type]=contains&where[0][attribute]=phoneNumber&where[0][value]={digits}")
        if result and result.get("list"):
            return result["list"][0]
        return None


# 单例
_client: Optional[EspoCRMClient] = None


def get_espocrm() -> EspoCRMClient:
    global _client
    if _client is None:
        _client = EspoCRMClient()
    return _client
