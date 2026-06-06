"""
WAHA ↔ Chatwoot 桥接中间层。

计划 §4.3 架构流程。
"""

import json
import logging
from typing import Any, Optional
import requests

from .config import WAHA_URL, WAHA_API_KEY, CHATWOOT_URL, CHATWOOT_API_TOKEN, CHATWOOT_ACCOUNT_ID, CHATWOOT_INBOX_ID
from .espocrm_client import get_espocrm
from .state_store import hget, hset, hdel

logger = logging.getLogger("waha_bridge")

# contact_id → WA chatId 映射（Redis 持久化，7 天 TTL 由 state_store 管理）
WA_MAPPING_HASH = "wa_chat_ids"


class WahaBridge:
    """WAHA 和 Chatwoot 之间的消息桥接。"""

    def __init__(self):
        self._waha = f"{WAHA_URL}/api"
        self._waha_headers = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}
        self._cw_url = CHATWOOT_URL
        self._cw_token = CHATWOOT_API_TOKEN
        self._cw_account = CHATWOOT_ACCOUNT_ID
        self._cw_inbox = CHATWOOT_INBOX_ID

    def handle_waha_message(self, payload: dict) -> dict:
        """处理 WAHA webhook 推送的新消息。"""
        event = payload.get("event", "")
        if event != "message":
            return {"status": "ignored", "event": event}

        body = payload.get("payload", {})
        wa_chat_id = body.get("from", "")  # e.g. 156255993749734@lid
        text = body.get("body", "") or body.get("text", {}).get("text", "")

        if not wa_chat_id or not text:
            return {"status": "missing_fields"}

        # 客户名：WA notifyName
        sender_name = body.get("_data", {}).get("notifyName", "")
        if not sender_name:
            parts = wa_chat_id.split("@")[0]
            sender_name = f"WA:{parts[:12]}"

        # Chatwoot phone: E.164 格式要求 + 前缀
        cw_phone = f"+{wa_chat_id.split('@')[0].lstrip('+')}"

        contact_id = self._find_or_create_contact(sender_name, cw_phone)
        if not contact_id:
            return {"status": "contact_failed"}

        # 保存 chat_id → 回复时用（Redis 持久化）
        hset(WA_MAPPING_HASH, str(contact_id), wa_chat_id)

        conversation = self._create_or_append_conversation(contact_id, f"wa_{cw_phone[:50]}", text)
        if conversation:
            conv_id = conversation.get("id")
            logger.info(f"[Bridge] conv={conv_id} contact={contact_id}")

            # EspoCRM
            phone = self._extract_phone(wa_chat_id) if "@c.us" in wa_chat_id else ""
            if phone:
                espocrm = get_espocrm()
                lead = espocrm.find_lead_by_phone(phone)
                if not lead:
                    espocrm.create_lead({"name": sender_name, "phone": phone, "source": "inbound_whatsapp"})

            return {"status": "ok", "conv_id": conv_id}

        return {"status": "ok", "conv_id": None}

    def _extract_phone(self, wa_id: str) -> str:
        phone = wa_id.split("@")[0] if "@" in wa_id else wa_id
        return f"+{phone}" if not phone.startswith("+") else phone

    def _find_or_create_contact(self, name: str, phone: str) -> Optional[int]:
        """查找或创建 Chatwoot Contact。"""
        headers = {"api_access_token": self._cw_token, "Content-Type": "application/json"}
        # 搜索
        for q in [phone, phone.split("@")[0]]:
            try:
                resp = requests.get(
                    f"{self._cw_url}/api/v1/accounts/{self._cw_account}/contacts/search",
                    params={"q": q}, headers=headers, timeout=10,
                )
                if resp.status_code == 200:
                    p = resp.json().get("payload", [])
                    if p:
                        logger.info(f"[Bridge] Contact found: {p[0]['id']}")
                        return p[0]["id"]
            except Exception:
                pass
        # 创建
        try:
            resp = requests.post(
                f"{self._cw_url}/api/v1/accounts/{self._cw_account}/contacts",
                headers=headers,
                json={"name": name, "phone_number": phone},
                timeout=10,
            )
            if resp.status_code == 200:
                cid = resp.json().get("payload", {}).get("contact", {}).get("id")
                if cid:
                    logger.info(f"[Bridge] Contact created: {cid}")
                    return cid
            logger.warning(f"[Bridge] Contact create: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logger.error(f"[Bridge] Contact error: {e}")
        return None

    def _create_or_append_conversation(self, contact_id: int, source_id: str, text: str) -> Optional[dict]:
        """查找已有 OPEN 对话追加消息，没有则创建新对话。"""
        headers = {"api_access_token": self._cw_token, "Content-Type": "application/json"}
        # 1. 查找该 contact 已存在的 OPEN 对话
        try:
            resp = requests.get(
                f"{self._cw_url}/api/v1/accounts/{self._cw_account}/conversations",
                params={"inbox_id": self._cw_inbox, "status": "open"},
                headers=headers, timeout=5,
            )
            if resp.status_code == 200:
                convs = resp.json().get("data", {}).get("payload", [])
                for c in convs:
                    sender = c.get("meta", {}).get("sender", {})
                    if sender.get("id") == contact_id:
                        conv_id = c["id"]
                        # 追加消息到已有对话
                        resp2 = requests.post(
                            f"{self._cw_url}/api/v1/accounts/{self._cw_account}/conversations/{conv_id}/messages",
                            headers=headers,
                            json={"content": text, "message_type": "incoming"},
                            timeout=10,
                        )
                        if resp2.status_code == 200:
                            logger.info(f"[Bridge] Appended to conv={conv_id}")
                            return c
        except Exception as e:
            logger.warning(f"[Bridge] Search convs error: {e}")

        # 2. 没有则创建新对话
        try:
            resp = requests.post(
                f"{self._cw_url}/api/v1/accounts/{self._cw_account}/conversations",
                headers=headers,
                json={"source_id": source_id, "inbox_id": self._cw_inbox,
                      "contact_id": contact_id, "message": {"content": text, "message_type": "incoming"}},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                logger.info(f"[Bridge] New conv created")
                return resp.json()
        except Exception as e:
            logger.error(f"[Bridge] Conv create error: {e}")
        return None

    def send_chatwoot_reply(self, conversation_id: int, message: str) -> bool:
        """Chatwoot webhook → RAG → WAHA 发回。"""
        headers = {"api_access_token": self._cw_token}
        try:
            resp = requests.get(
                f"{self._cw_url}/api/v1/accounts/{self._cw_account}/conversations/{conversation_id}",
                headers=headers, timeout=10,
            )
            if resp.status_code != 200:
                return False
            conv = resp.json()
            contact_id = conv.get("meta", {}).get("sender", {}).get("id")
            if not contact_id:
                return False
        except Exception:
            return False

        # 从 Redis 持久化映射找 WA chatId
        wa_chat_id = hget(WA_MAPPING_HASH, str(contact_id)) or ""
        if not wa_chat_id:
            # fallback: 从 contact phone 推断
            try:
                resp2 = requests.get(
                    f"{self._cw_url}/api/v1/accounts/{self._cw_account}/contacts/{contact_id}",
                    headers=headers, timeout=5,
                )
                if resp2.status_code == 200:
                    phone = resp2.json().get("payload", {}).get("phone_number", "")
                    digits = "".join(c for c in phone if c.isdigit())
                    if len(digits) >= 14:
                        wa_chat_id = f"{digits}@lid"
                    else:
                        wa_chat_id = f"{digits}@c.us"
            except Exception:
                pass

        if not wa_chat_id:
            return False

        logger.info(f"[Bridge] Replying to {contact_id} via {wa_chat_id[:30]}")
        return self._waha_send_text(wa_chat_id, message)

    def _waha_send_text(self, chat_id: str, text: str, session: str = "default") -> bool:
        try:
            resp = requests.post(
                f"{self._waha}/sendText", headers=self._waha_headers,
                json={"chatId": chat_id, "text": text, "session": session}, timeout=15,
            )
            ok = resp.status_code in (200, 201)
            prefix = "OK" if ok else f"ERR {resp.status_code}"
            logger.info(f"[Bridge] WAHA {prefix}: {chat_id[:25]} -> {text[:40]}")
            return ok
        except Exception as e:
            logger.error(f"[Bridge] WAHA error: {e}")
            return False

    def health_check(self) -> dict:
        try:
            resp = requests.get(f"{self._waha}/sessions/default", headers=self._waha_headers, timeout=5)
            return {"waha": "connected", "status": resp.json().get("status", "?")}
        except Exception as e:
            return {"waha": f"error: {e}"}


_bridge: Optional[WahaBridge] = None


def get_bridge() -> WahaBridge:
    global _bridge
    if _bridge is None:
        _bridge = WahaBridge()
    return _bridge
