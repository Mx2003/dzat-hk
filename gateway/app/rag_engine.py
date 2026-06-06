"""
RAG 引擎 — DeepSeek 多语言客服。

支持任意语言：DeepSeek 原生理解 20+ 语言，自动检测并以客户语言回复。
FAQ 知识库作为参考，所有匹配和分类由 LLM 完成（不再依赖关键词）。
"""

import json
import logging
from pathlib import Path
from typing import Optional
import requests

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_FLASH_MODEL, KNOWLEDGE_DIR

logger = logging.getLogger("rag_engine")

# ── 知识库（FAQ 参考，LLM 会按客户语言改写）───────

_FAQ_KNOWLEDGE = {
    "moq": "ODM MOQ: 5,000 units/SKU | OEM MOQ: 10,000 units/SKU | Stock: 500 units.",
    "pricing": "Disposable vapes: $3.5-$12/unit | Pod systems: $5-$15/unit. Exact pricing depends on order volume and customization.",
    "lead_time": "Samples: 5-7 working days | Mass production: 25-35 days after deposit.",
    "sample": "Sample fee: $50-$150/model (refunded on orders over $5,000).",
    "payment": "30% deposit, 70% before shipment. First order over $10,000: 5% discount.",
    "warranty": "Free replacement for manufacturing defects. Extended warranty available for bulk orders.",
    "factory": "Welcome to visit! 1-2 weeks advance notice. We'll arrange factory tour + team meeting + accommodation tips.",
    "oem_odm": "DZAT specializes in ODM/OEM. Customize device design, packaging, flavors. ODM MOQ: 5,000 | OEM MOQ: 10,000.",
    "certification": "ISO 9001, CE, RoHS, EMC, LVD, REACH. We also support FDA, UKCA, TPD, HC for target markets.",
}

class RAGEngine:
    """DeepSeek 多语言 RAG 引擎。"""

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
        """加载知识库文件到内存。"""
        parts = []
        for f in KNOWLEDGE_DIR.glob("*.json"):
            try:
                parts.append(f.read_text(encoding="utf-8")[:8000])
            except Exception:
                pass
        for f in KNOWLEDGE_DIR.glob("*.txt"):
            try:
                parts.append(f.read_text(encoding="utf-8")[:8000])
            except Exception:
                pass
        return "\n".join(parts) if parts else ""

    def _format_faq_knowledge(self) -> str:
        """格式化 FAQ 为 LLM 参考文本。"""
        return "\n".join(f"- {k}: {v}" for k, v in _FAQ_KNOWLEDGE.items())

    # ── FAQ 关键词快速匹配 ──────────────────────

    def _faq_match(self, text: str) -> Optional[str]:
        """关键词快速匹配 FAQ — 只用英文/中文关键词（B2B 通用术语）。

        只有消息明显是英文或中文时才走快速匹配，避免在日语/西语等
        消息中误匹配（比如日语消息包含 "MOQ" 不是英文对话）。
        """
        lowered = text.lower()

        # 快速判断：如果消息有大量非英文字符，很可能是其他语言
        non_en = sum(1 for c in text if c > '\x7f')
        total = len(text)
        # 超过 20% 非 ASCII 字符 → 跳过快速匹配，走 LLM
        if total > 5 and non_en / total > 0.2:
            return None

        keywords = {
            "moq": ["moq", "minimum order", "min order", "起订量", "最少订", "多少量"],
            "pricing": ["price", "pricing", "cost", "报价", "价格", "多少钱", "how much"],
            "lead_time": ["lead time", "delivery", "交期", "多久交货"],
            "sample": ["sample", "样品", "样板", "muster", "サンプル"],
            "payment": ["payment", "付款", "deposit", "定金"],
            "warranty": ["warranty", "保修", "guarantee"],
            "factory": ["factory", "visit", "参观"],
            "oem_odm": ["oem", "odm", "定制", "custom", "カスタム"],
            "certification": ["certification", "认证", "fda", "ce", "rohs"],
        }
        for topic, kws in keywords.items():
            if any(kw in lowered for kw in kws):
                logger.info(f"[RAG] FAQ match: {topic}")
                return _FAQ_KNOWLEDGE.get(topic)
        return None

    # ── 意图分类（多语言关键词）─────────────────

    # 意图关键词覆盖：英/中/西/法/德/阿/葡/俄/日/韩
    _INTENT_KEYWORDS = {
        "human_request": [
            "human", "agent", "representative", "person", "staff", "manager", "real person",
            "人工", "客服", "真人", "转接", "转人工", "人员",
            "humano", "agente", "persona", "real",
            "humain", "agent", "personne", "réel",
            "mensch", "mitarbeiter", "persönlich",
            "إنسان", "وكيل", "شخص", "حقيقي", "موظف",
            "humano", "atendente", "pessoa",
            "человек", "оператор", "сотрудник", "живой",
            "人間", "担当者", "オペレーター", "人",
            "사람", "상담원", "담당자",
        ],
        "order": [
            "order", "buy", "purchase", "下单", "订购", "购买",
            "pedido", "comprar", "orden",
            "commander", "acheter", "ordre",
            "bestellen", "kaufen",
            "طلب", "شراء",
            "encomendar", "comprar",
            "заказ", "купить", "оплат", "счет",
            "注文", "購入",
            "주문", "구매",
        ],
        "support": [
            "broken", "not working", "defect", "damaged", "坏了", "不能用", "问题",
            "roto", "defectuoso", "no funciona",
            "cassé", "défectueux", "ne fonctionne pas",
            "kaputt", "defekt", "funktioniert nicht",
            "مكسور", "معطل", "لا يعمل",
            "quebrado", "com defeito",
            "сломан", "не работает",
            "壊れ", "故障",
            "고장", "작동",
        ],
        "inquiry": [
            "price", "moq", "sample", "payment", "delivery", "shipping", "how", "what", "tell me", "oem", "odm", "know",
            "价格", "多少钱", "交期", "样品", "付款", "运费", "定制",
            "precio", "cuánto", "costo", "muestra",
            "prix", "combien", "coût", "échantillon",
            "preis", "kosten", "muster",
            "سعر", "تكلفة", "شحن", "عينة",
            "preço", "quanto", "custo", "saber",
            "цена", "сколько", "доставка",
            "価格", "いくら", "送料",
            "가격", "비용", "배송",
        ],
    }

    def classify_intent(self, message: str) -> str:
        """分类客户意图 — 多语言关键词，无需 API 调用。

        Returns: inquiry / order / support / human_request / other
        """
        lowered = message.lower()
        for intent, keywords in self._INTENT_KEYWORDS.items():
            if any(kw in lowered for kw in keywords):
                return intent
        return "other"

    # ── AI 回复生成（多语言）────────────────────

    def generate_reply(self, message: str, conversation_history: list[dict] = None) -> str:
        """DeepSeek 生成多语言客服回复。

        自动检测客户语言并以同语言回复。FAQ 匹配也由 LLM 完成，
        避免关键词在非英文消息中误匹配导致返回英文答案。
        """
        knowledge = self._knowledge[:3000] or self._format_faq_knowledge()

        # 最近对话历史
        history_text = ""
        if conversation_history:
            recent = conversation_history[-4:]
            history_text = "\n".join(
                f"{'Customer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
                for m in recent
            )

        system = f"""You are a professional sales representative for DZATVAPE, a Chinese ODM/OEM manufacturer of electronic cigarettes and cannabis devices (10+ years, ISO/GMP certified).

Products: Disposable vapes, pod systems, CBD/THC devices, dry herb vaporizers.
Advantages: 45-day R&D cycle, 4M monthly capacity, flexible ODM/OEM, transparent pricing.

FAQ quick reference (use as needed, adapt to customer's language):
{self._format_faq_knowledge()}

Company knowledge:
{knowledge}

CRITICAL LANGUAGE RULES (highest priority):
1. Look at the CURRENT customer message to determine the language. Reply in THAT language.
2. Even if the conversation history is in a different language, always use the language of the LATEST customer message.
3. If a customer switches from English to Japanese mid-conversation, you MUST switch to Japanese too.
4. NEVER reply in English when the current message is not in English.
5. Be professional, warm, concise. 2-4 sentences max.
6. If the customer asks for a human, suggest transferring and ask them to wait.
7. For pricing/MOQ beyond your knowledge, invite the customer to discuss details with a specialist.
8. Never make up specifications or prices you don't know.
9. End with an engaging question when appropriate."""

        # 先 FAQ 快速匹配 — 但如果客户消息不是纯英文/中文则跳过（避免误匹配）
        faq = self._faq_match(message)
        if faq:
            # FAQ 命中 → 让 LLM 翻译成客户语言
            return self._translate_faq(faq, message)

        messages = [{"role": "system", "content": system}]
        if history_text:
            messages.append({"role": "user", "content": f"Conversation history:\n{history_text}"})
        messages.append({"role": "user", "content": message})

        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json={"model": self._model, "messages": messages, "temperature": 0.5, "max_tokens": 500},
                timeout=25,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content.strip():
                    logger.info(f"[RAG] Generated reply ({len(content)} chars)")
                    return content.strip()
        except Exception as e:
            logger.error(f"[RAG] DeepSeek error: {e}")

        # 降级：尝试用客户语言返回通用消息
        return self._multilingual_fallback(message)

    def _translate_faq(self, faq_text: str, customer_message: str) -> str:
        """用 LLM 把 FAQ 答案翻译成客户语言。"""
        prompt = f"""Translate this FAQ answer to match the language of the customer's message.
Customer message: "{customer_message[:200]}"

FAQ answer (English):
{faq_text}

Reply ONLY with the translated text in the customer's language. Keep it concise and professional."""

        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if content.strip():
                    logger.info(f"[RAG] Translated FAQ to customer language")
                    return content.strip()
        except Exception as e:
            logger.warning(f"[RAG] FAQ translation failed: {e}")

        # 翻译失败，走完整 LLM
        return self.generate_reply(customer_message, None)

    def _multilingual_fallback(self, message: str) -> str:
        """生成多语言降级回复。用简单启发式判断语言。"""
        # 快速语言检测
        lang_hints = {
            "zh": "感谢您的留言！请稍等，我们的销售团队会尽快回复您。或回复'人工'直接联系真人客服。",
            "es": "¡Gracias por contactarnos! Nuestro equipo de ventas le responderá pronto. Responda 'human' para hablar con una persona.",
            "fr": "Merci de nous avoir contactés ! Notre équipe commerciale vous répondra bientôt. Répondez 'human' pour parler à une personne.",
            "de": "Vielen Dank für Ihre Nachricht! Unser Vertriebsteam wird Ihnen in Kürze antworten. Antworten Sie 'human', um mit einer Person zu sprechen.",
            "ar": "شكرا لتواصلك معنا! سيرد عليك فريق المبيعات قريبا. أرسل 'human' للتحدث مع شخص حقيقي.",
            "pt": "Obrigado por nos contactar! Nossa equipe de vendas responderá em breve. Responda 'human' para falar com uma pessoa.",
            "ru": "Спасибо за обращение! Наша команда продаж ответит вам в ближайшее время. Ответьте 'human', чтобы связаться с оператором.",
            "ja": "お問い合わせありがとうございます。営業チームがまもなく返信いたします。担当者につなぐには「human」と返信してください。",
            "ko": "문의해 주셔서 감사합니다. 영업팀이 곧 답변드리겠습니다. 담당자와 연결하려면 'human'이라고 답장하세요.",
        }

        # 检测常见语言特征
        lowered = message.lower()
        for char, lang in [("¿", "es"), ("ñ", "es"), ("é", "fr"), ("è", "fr"), ("ê", "fr"),
                           ("ü", "de"), ("ö", "de"), ("ä", "de"), ("ß", "de"),
                           ("ا", "ar"), ("ل", "ar"), ("ع", "ar"),
                           ("ã", "pt"), ("õ", "pt"), ("ç", "pt"),
                           ("ы", "ru"), ("й", "ru"), ("ц", "ru"),
                           ("ん", "ja"), ("を", "ja"), ("は", "ja"),
                           ("합", "ko"), ("습", "ko"), ("니", "ko"),
                           ]:
            if char in message:
                return lang_hints.get(lang, lang_hints["zh"])

        # 中文检测
        if any('一' <= c <= '鿿' for c in message):
            return lang_hints["zh"]

        # 默认英文
        return "Thanks for reaching out! Our sales team will get back to you shortly. Reply 'human' to connect with a real person."

    # ── 转人工判断 ──────────────────────────────

    def should_handoff(self, conversation_history: list[dict]) -> bool:
        """判断是否应该转人工。

        触发条件：
        1. 客户明确请求人工（多语言关键词检测）
        2. 客户连发 3 条消息仍未解决
        """
        if not conversation_history:
            return False

        # 检查是否有明确的人工请求
        last_customer_msg = ""
        for m in reversed(conversation_history):
            if m.get("role") == "user":
                last_customer_msg = m.get("content", "")
                break

        if self.classify_intent(last_customer_msg) == "human_request":
            return True

        # 客户发了 3+ 条消息，可能问题未被解决
        customer_msgs = [m for m in conversation_history if m.get("role") == "user"]
        if len(customer_msgs) >= 3:
            return True

        return False

    def health_check(self) -> dict:
        return {
            "engine": "DeepSeek RAG (multilingual)",
            "knowledge": "loaded" if self._knowledge else "faq_only",
            "model": self._model,
            "languages": "auto-detect (20+ languages supported)",
        }


# 单例
_rag: Optional[RAGEngine] = None


def get_rag() -> RAGEngine:
    global _rag
    if _rag is None:
        _rag = RAGEngine()
    return _rag
