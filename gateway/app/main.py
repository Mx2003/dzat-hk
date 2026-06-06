"""
DZAT Gateway API — FastAPI。

计划 §三 目标架构：一体三职 — API 编排中枢 + RAG 后端 + 定时调度。
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import WAHA_URL, CHATWOOT_URL
from .waha_bridge import get_bridge
from .rag_engine import get_rag
from .espocrm_client import get_espocrm
from .wechat_notify import get_notifier
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

import requests as _requests
from .config import CHATWOOT_URL, CHATWOOT_API_TOKEN, CHATWOOT_ACCOUNT_ID
from .state_store import get, set, delete, health_check as store_health

# ── Redis-backed state (survives restarts) ──────

def _conv_store_get(conv_key: str) -> list[dict]:
    return get(f"conv:{conv_key}") or []

def _conv_store_append(conv_key: str, msg: dict):
    history = _conv_store_get(conv_key)
    history.append(msg)
    set(f"conv:{conv_key}", history, ttl=172800)  # 48h TTL

def _conv_store_set_handoff(conv_key: str, ts: float):
    set(f"handoff:{conv_key}", ts, ttl=1800)  # 30min

def _conv_store_get_handoff(conv_key: str) -> float:
    return get(f"handoff:{conv_key}") or 0

def _ai_paused_get(conv_id: int) -> bool:
    return get(f"pause:{conv_id}") or False

def _ai_paused_set(conv_id: int, paused: bool):
    set(f"pause:{conv_id}", paused, ttl=86400)  # 24h TTL

def _last_reply_get(conv_id: int) -> str:
    return get(f"last_reply:{conv_id}") or ""

def _last_reply_set(conv_id: int, content: str):
    set(f"last_reply:{conv_id}", content, ttl=300)  # 5min dedup

def _last_reply_clear(conv_id: int):
    delete(f"last_reply:{conv_id}")


def _fetch_chatwoot_messages(conversation_id: int) -> list[dict]:
    """从 Chatwoot API 获取对话消息历史。"""
    try:
        resp = _requests.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
            headers={"api_access_token": CHATWOOT_API_TOKEN},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            messages = []
            for m in data.get("payload", []):
                msg_type = "assistant" if m.get("message_type") == 1 else "user"
                messages.append({"role": msg_type, "content": m.get("content", "")})
            return list(reversed(messages))
    except Exception:
        pass
    return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[Gateway] starting — {datetime.now()}")
    start_scheduler()
    yield
    logger.info(f"[Gateway] shutting down")
    stop_scheduler()


app = FastAPI(title="DZAT B2B Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── 健康检查 ─────────────────────────────────────

@app.get("/api/health")
async def health():
    bridge = get_bridge()
    rag = get_rag()
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "waha": bridge.health_check().get("waha", "unknown"),
        "rag": rag.health_check().get("engine", "unknown"),
    }


# ── WAHA Webhook ─────────────────────────────────

@app.post("/api/waha/webhook")
async def waha_webhook(payload: dict):
    logger.info(f"[WAHA] webhook: {payload.get('event', 'unknown')}")
    bridge = get_bridge()
    result = bridge.handle_waha_message(payload)
    return result


# ── Chatwoot Webhook ─────────────────────────────

@app.post("/api/chatwoot/webhook")
async def chatwoot_webhook(payload: dict):
    event = payload.get("event", "")
    conversation_id = payload.get("conversation", {}).get("id", payload.get("id", 0))
    logger.info(f"[Chatwoot] event: {event}")

    # ── 分配事件 → AI 暂停/恢复 ─────────────────
    if event == "conversation.updated":
        logger.info(f"[Chatwoot] conv_updated full: {str(payload)[:500]}")
        assignee = payload.get("meta", {}).get("assignee", {})
        old_assignee = payload.get("changes", {}).get("assignee_id", [])
        now_assigned = bool(assignee.get("id"))
        was_assigned = old_assignee and old_assignee[0] is not None if len(old_assignee) > 0 else False
        if now_assigned and not was_assigned:
            _ai_paused_set(conversation_id, True)
            logger.info(f"[Chatwoot] Agent assigned → AI paused for conv={conversation_id}")
        elif not now_assigned and was_assigned:
            _ai_paused_set(conversation_id, False)
            logger.info(f"[Chatwoot] Agent unassigned → AI resumed for conv={conversation_id}")
        return {"status": "assignment_handled"}

    if event != "message_created":
        return {"status": "ignored"}

    content = payload.get("content", "")
    conversation_id = payload.get("conversation", {}).get("id", 0)
    sender = payload.get("sender", {})
    sender_type = sender.get("type", "")

    # ── Agent/销售 回复 ──────────────────────────
    if sender_type == "user" and sender.get("id") != sender.get("contact_id"):
        # 跳过网关自己发的消息（防自触发暂停）
        if _last_reply_get(conversation_id) == content or content.startswith("🤖") or content.startswith("🔴"):
            _last_reply_clear(conversation_id)
            return {"status": "skipped_own_reply"}

        logger.info(f"[Chatwoot] Agent reply: {content[:50]}")

        cmd = content.strip().lower()
        if cmd in ("ai on", "ai resume", "/ai on", "/ai resume"):
            _ai_paused_set(conversation_id, False)
            logger.info(f"[Chatwoot] AI resumed for conv={conversation_id}")
            _requests.post(
                f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
                headers={"api_access_token": CHATWOOT_API_TOKEN},
                json={"content": "🤖 AI 已恢复自动回复", "message_type": "outgoing", "private": True},
                timeout=5,
            )
            bridge = get_bridge()
            bridge.send_chatwoot_reply(conversation_id, content)
            return {"status": "ai_resumed"}
        elif cmd in ("ai off", "ai pause", "/ai off", "/ai pause"):
            _ai_paused_set(conversation_id, True)
            logger.info(f"[Chatwoot] AI paused manually for conv={conversation_id}")
            _requests.post(
                f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
                headers={"api_access_token": CHATWOOT_API_TOKEN},
                json={"content": "🔴 AI 已暂停自动回复", "message_type": "outgoing", "private": True},
                timeout=5,
            )
            bridge = get_bridge()
            bridge.send_chatwoot_reply(conversation_id, content)
            return {"status": "ai_paused"}
        else:
            # 销售发消息 → 暂停 AI
            _ai_paused_set(conversation_id, True)
            logger.info(f"[Chatwoot] AI paused for conv={conversation_id}")

        # 转发到 WAHA
        bridge = get_bridge()
        sent = bridge.send_chatwoot_reply(conversation_id, content)
        return {"status": "forwarded_to_waha" if sent else "forward_failed"}

    # ── 客户消息 → RAG 处理 ──────────────────────
    if sender_type not in ("contact", "user", ""):
        return {"status": "ignored", "reason": f"sender={sender_type}"}
    if not content:
        return {"status": "ignored", "reason": "no content"}

    conversation_key = f"conv_{conversation_id}"
    logger.info(f"[RAG] processing: conv={conversation_id} content={content[:50]}")

    # 客户发消息 → 如果之前被销售暂停，检测是否恢复
    customer_name = sender.get("name", "Customer")

    # 加载/创建对话历史（Redis 持久化）
    conversation_history = _conv_store_get(conversation_key)
    _conv_store_append(conversation_key, {"role": "user", "content": content})
    conversation_history.append({"role": "user", "content": content})

    # ── AI 暂停检查 ──────────────────────────────
    if _ai_paused_get(conversation_id):
        logger.info(f"[RAG] AI paused for conv={conversation_id}, skipping auto-reply")
        # 仍然检查转人工提醒
        rag = get_rag()
        notifier = get_notifier()
        if rag.should_handoff(conversation_history):
            _send_handoff(conversation_key, conversation_id, customer_name, sender, notifier, rag)
        return {"status": "ai_paused", "reason": "human handling conversation"}

    # ── RAG 引擎处理 ──────────────────────────────
    rag = get_rag()
    notifier = get_notifier()

    # 转人工提醒
    if rag.should_handoff(conversation_history):
        _send_handoff(conversation_key, conversation_id, customer_name, sender, notifier, rag)

    # AI 生成回复
    reply = rag.generate_reply(content, conversation_history)
    _conv_store_append(conversation_key, {"role": "assistant", "content": reply})
    conversation_history.append({"role": "assistant", "content": reply})

    # WAHA 发回
    bridge = get_bridge()
    sent = bridge.send_chatwoot_reply(conversation_id, reply)

    # 写入 Chatwoot（标记本次回复防自触发）
    _last_reply_set(conversation_id, reply)
    try:
        _requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
            headers={"api_access_token": CHATWOOT_API_TOKEN},
            json={"content": reply, "message_type": "outgoing", "private": False},
            timeout=5,
        )
    except Exception:
        _last_reply_clear(conversation_id)

    return {"status": "replied" if sent else "reply_failed", "reply": reply[:200]}


def _send_handoff(conv_key: str, conv_id: int, customer_name: str, sender: dict, notifier, rag):
    """发送转人工通知（30 分钟去重）。"""
    import time as _time
    now_ts = _time.time()
    last_time = _conv_store_get_handoff(conv_key)
    if now_ts - last_time < 1800:
        return
    _conv_store_set_handoff(conv_key, now_ts)

    conv_history = _conv_store_get(conv_key)
    raw_phone = sender.get("phone_number", "")
    digits = "".join(c for c in raw_phone if c.isdigit())
    display_phone = raw_phone if len(digits) <= 13 else "WhatsApp"
    all_msgs = [m["content"] for m in conv_history if m["role"] == "user"]
    full_history = _fetch_chatwoot_messages(conv_id) or conv_history
    conv_summary = "\n> ".join(
        f"{'[客户]' if m['role']=='user' else '[AI]'} {m['content'][:80]}"
        for m in full_history[-8:]
    )
    trigger = "3轮对话自动转接" if len(all_msgs) >= 3 and rag.classify_intent(all_msgs[-1]) != "human_request" else "客户明确请求人工"

    logger.info(f"[RAG] handoff: {conv_id}")
    notifier.notify_handoff(
        customer_name=customer_name, phone=display_phone, language="auto",
        trigger_reason=trigger, customer_msgs=all_msgs,
        conversation_summary=f"> {conv_summary}" if conv_summary else "",
    )


# ── RAG 测试接口 ────────────────────────────────

@app.get("/api/rag/search")
async def rag_search(q: str = ""):
    rag = get_rag()
    faq = rag._faq_match(q)
    if faq:
        return {"query": q, "match": "faq", "answer": faq}
    return {"query": q, "match": "none"}


# ── 桥接状态 ─────────────────────────────────────

@app.get("/api/bridge/status")
async def bridge_status():
    bridge = get_bridge()
    return bridge.health_check()


# ── 获客引擎 (LangGraph) ────────────────────────

@app.post("/api/discovery/run")
async def trigger_discovery():
    from .discovery.graph import run_discovery
    result = run_discovery(max_rounds=3)
    return {"status": "ok", "rounds": result.get("round_count", 0),
            "new_leads": len(result.get("new_lead_ids", [])),
            "history": result.get("history", [])[-5:]}


# ── 触达系统 ────────────────────────────────────

@app.post("/api/outreach/run")
async def trigger_outreach(platform: str = "all"):
    from .outreach.dispatcher import OutreachDispatcher
    d = OutreachDispatcher()
    if platform == "all":
        results = d.run_all()
    else:
        results = {platform: d.dispatch_platform(platform)}
    summary = {p: f"{len(rs)} sent" for p, rs in results.items() if rs}
    return {"status": "ok", "summary": summary}


# ── AI 接管状态 ─────────────────────────────────

@app.get("/api/ai/status")
async def ai_status():
    from .state_store import scan_keys
    return {
        "paused_conversations": scan_keys("pause:*"),
        "active_conversations": scan_keys("conv:*"),
        "redis": store_health(),
    }
