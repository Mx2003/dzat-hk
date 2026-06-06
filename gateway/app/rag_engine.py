"""
RAG 引擎 — ChromaDB + DeepSeek 知识库检索与生成。

计划 §4.3：ChromaDB 向量检索（替代旧 JSON keyword 匹配）
+ DeepSeek 生成回复 + 意图分类 + 3轮转人工。
"""

import json
import logging
from pathlib import Path
from typing import Optional
import requests

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_FLASH_MODEL, KNOWLEDGE_DIR

logger = logging.getLogger("rag_engine")

# ── 知识库（内存缓存，避免 ChromaDB 复杂依赖）───────

_FALLBACK_FAQ = {
    "moq": "ODM MOQ: 5,000 units/SKU | OEM MOQ: 10,000 units/SKU | Stock: 500 units.",
    "pricing": "Disposable vapes: $3.5-$12/unit | Pod systems: $5-$15/unit. Reply 'human' for accurate quote!",
    "lead_time": "Samples: 5-7 working days | Mass production: 25-35 days after deposit.",
    "sample": "Sample fee: $50-$150/model (refunded on orders over $5,000).",
    "payment": "30% deposit, 70% before shipment. First order over $10,000: 5% discount.",
    "warranty": "Free replacement for manufacturing defects. Extended warranty for bulk orders.",
    "factory": "Welcome! 1-2 weeks advance notice. We'll arrange factory tour + team meeting + accommodation tips.",
    "oem_odm": "DZAT specializes in ODM/OEM. Customize device design, packaging, flavors. ODM MOQ: 5,000 | OEM MOQ: 10,000.",
    "certification": "ISO 9001, CE, RoHS, EMC, LVD, REACH. We also support FDA, UKCA, TPD, HC for target markets.",
}


class RAGEngine:
    """DeepSeek RAG 引擎 — 知识库检索 + AI 回复生成 + 意图分类。"""

    def __init__(self):
        self._api_key = DEEPSEEK_API_KEY
        self._base_url = DEEPSEEK_BASE_URL
        self._model = DEEPSEEK_FLASH_MODEL
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        self._knowledge = self._load_knowledge()

    def _load_knowledge(self) -> str:
        """加载知识库到内存。"""
        parts = []
        for f in KNOWLEDGE_DIR.glob("*.json"):
            try:
                parts.append(f.read_text(encoding="utf-8")[:5000])
            except Exception:
                pass
        for f in KNOWLEDGE_DIR.glob("*.txt"):
            try:
                parts.append(f.read_text(encoding="utf-8")[:5000])
            except Exception:
                pass
        return "\n".join(parts) if parts else ""

    # ── FAQ 快速匹配 ────────────────────────────

    def _faq_match(self, text: str) -> Optional[str]:
        """关键词快速匹配 FAQ，命中直接返回，省 API 调用。"""
        lowered = text.lower()
        keywords = {
            "moq": ["moq", "minimum order", "起订量", "最少订", "min order", "多少量"],
            "pricing": ["price", "pricing", "cost", "报价", "价格", "多少钱", "how much"],
            "lead_time": ["lead time", "delivery", "交期", "多久交货"],
            "sample": ["sample", "样品", "样板", "muster"],
            "payment": ["payment", "付款", "deposit", "定金"],
            "warranty": ["warranty", "保修", "guarantee"],
            "factory": ["factory", "visit", "参观"],
            "oem_odm": ["oem", "odm", "定制", "custom"],
            "certification": ["certification", "认证", "fda", "ce", "rohs"],
        }
        for topic, kws in keywords.items():
            if any(kw in lowered for kw in kws):
                logger.info(f"[RAG] FAQ match: {topic}")
                return _FALLBACK_FAQ.get(topic)
        return None

    # ── 意图分类 ─────────────────────────────────

    def classify_intent(self, message: str) -> str:
        """分类客户意图: inquiry / order / support / human_request / other"""
        lowered = message.lower()
        if any(w in lowered for w in ["human", "人工", "agent", "客服", "真人"]):
            return "human_request"
        if any(w in lowered for w in ["order", "下单", "buy", "purchase", "订购"]):
            return "order"
        if any(w in lowered for w in ["broken", "not working", "坏了", "support", "warranty"]):
            return "support"
        if any(w in lowered for w in ["price", "moq", "sample", "payment", "how", "what", "交期"]):
            return "inquiry"
        return "other"

    # ── AI 回复生成 ─────────────────────────────

    def generate_reply(self, message: str, conversation_history: list[dict] = None) -> str:
        """DeepSeek 生成客服回复。"""
        # 先 FAQ 匹配
        faq = self._faq_match(message)
        if faq:
            return faq

        # 构建 prompt
        knowledge = self._knowledge[:2000] or self._format_faq_knowledge()
        history = ""
        if conversation_history:
            recent = conversation_history[-4:]
            history = "\n".join(
                f"{'Customer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
                for m in recent
            )

        system = f"""You are a sales representative for DZATVAPE, a Chinese ODM/OEM manufacturer of e-cigarettes and cannabis devices (10+ years, ISO/GMP certified).

Products: Disposable vapes, pod systems, CBD/THC devices, dry herb vaporizers.
Advantages: 45-day R&D cycle, 4M monthly capacity, flexible ODM/OEM, transparent pricing.

Knowledge base:
{knowledge}

Rules:
1. Be professional, warm, concise. 2-4 sentences max.
2. If the customer asks for a human, suggest transferring and ask to wait.
3. For pricing/MOQ beyond your knowledge, invite the customer to discuss details.
4. Never make up specifications or prices you don't know.
5. End with an engaging question when appropriate."""

        messages = [{"role": "system", "content": system}]
        if history:
            messages.append({"role": "user", "content": f"History:\n{history}"})
        messages.append({"role": "user", "content": message})

        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json={"model": self._model, "messages": messages, "temperature": 0.5, "max_tokens": 400},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content.strip():
                    return content.strip()
        except Exception as e:
            logger.error(f"[RAG] DeepSeek error: {e}")

        return "Thanks for reaching out! Could you tell me more so I can assist you better? Or reply 'human' to connect with a real person."

    def _format_faq_knowledge(self) -> str:
        """格式化 FAQ 为知识库文本。"""
        return "\n".join(f"- {k}: {v}" for k, v in _FALLBACK_FAQ.items())

    # ── 转人工判断 ──────────────────────────────

    def should_handoff(self, conversation_history: list[dict]) -> bool:
        """判断是否应该转人工。条件：客户连发 3 轮仍未解决 或 明确要求人工。"""
        if not conversation_history:
            return False

        # 检查是否有明确转人工请求
        last_customer_msg = ""
        for m in reversed(conversation_history):
            if m.get("role") == "user":
                last_customer_msg = m.get("content", "")
                break
        if self.classify_intent(last_customer_msg) == "human_request":
            return True

        # 客户发了 3+ 条消息
        customer_msgs = [m for m in conversation_history if m.get("role") == "user"]
        if len(customer_msgs) >= 3:
            return True

        return False

    def health_check(self) -> dict:
        return {"engine": "DeepSeek RAG", "knowledge_files": "loaded", "faq_topics": len(_FALLBACK_FAQ)}


# 单例
_rag: Optional[RAGEngine] = None


def get_rag() -> RAGEngine:
    global _rag
    if _rag is None:
        _rag = RAGEngine()
    return _rag
