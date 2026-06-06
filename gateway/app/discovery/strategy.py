"""
Strategy Agent — 市场选择 + 关键词生成。

关键词来源: keyword_bank 静态库（可靠）→ DeepSeek AI（增强）。
"""

import json
import logging
import random
import re

from typing import Any, Optional

from .keyword_bank import (
    NICOTINE_VAPE_CHANNEL, NICOTINE_VAPE_INTENT, NICOTINE_VAPE_SUPPLY_CHAIN,
    CANNABIS_DEVICE_CHANNEL, CANNABIS_DEVICE_INTENT, CANNABIS_DEVICE_SUPPLY_CHAIN,
    HIDDEN_GEM_SIGNALS, MULTILANG_KEYWORDS, TARGET_MARKETS, CN_TO_EN,
)

logger = logging.getLogger("discovery.strategy")

# 搜索策略（AI 增强时用）
SEARCH_STRATEGIES = {
    "A_brand_supply_chain": "跟踪品牌供应链：找大品牌授权经销商/分销商列表",
    "B_exhibition_replay": "展会复盘：找行业展会参展商名单",
    "C_industry_association": "行业协会渗透：找各国 vape 协会成员目录",
    "E_reverse_search": "反向搜索：用客户画像信号词反搜",
    "G_local_language": "非英语本地化搜索：小语种关键词找本地分销商",
}


class StrategyAgent:
    """决策本轮搜索目标+关键词。优先用静态关键词库。"""

    def decide(self, history: list[dict] = None, recent_yield: int = 0) -> dict[str, Any]:
        """返回: {market, strategy_key, keywords, product_line, reasoning}"""
        history = history or []

        # 选市场：轮换未产出或低产出的市场
        market = self._pick_market(history)

        # 生成关键词：渠道词 + 意向词 + 本地语言词
        keywords = self._generate_keywords(market)

        # 策略+产品线
        product_line = "nicotine_vape"
        if "cannabis_device" in market.get("legal", []):
            product_line = random.choice(["nicotine_vape", "cannabis_device"])

        strategy_key = "E_reverse_search"

        logger.info(f"[Strategy] {market['country']}/{market['city']}: {keywords[0][:50]}")
        return {
            "market": market, "strategy_key": strategy_key,
            "keywords": keywords, "product_line": product_line,
            "reasoning": f"静态关键词库: {len(keywords)} variants",
        }

    def _pick_market(self, history: list[dict]) -> dict:
        """选市场：优先选择尚未有产出的市场。"""
        # 统计每个市场的累计产出
        yields = {}
        for h in history:
            key = h.get("market", "")
            yields[key] = yields.get(key, 0) + h.get("leads", 0)

        # 低产出市场优先
        countries = list(TARGET_MARKETS.items())
        random.shuffle(countries)

        best = countries[0]
        for name, cfg in countries:
            if yields.get(name, 0) == 0:
                best = (name, cfg)
                break

        name, cfg = best
        cities = cfg.get("cities", ["Unknown"])
        city = random.choice(cities)
        return {"country": name, "city": city, "lang": cfg.get("lang", "en"), "legal": cfg.get("legal", [])}

    def _generate_keywords(self, market: dict) -> list[str]:
        """生成 6-10 个多样化关键词变体。"""
        country = market.get("country", "")
        country_en = CN_TO_EN.get(country, country)  # 搜索用英文国名
        city = market.get("city", "")
        lang = market.get("lang", "en")
        legal = market.get("legal", ["nicotine_vape"])

        product_line = "nicotine_vape"
        if "cannabis_device" in legal and random.random() > 0.5:
            product_line = "cannabis_device"

        # 选择基础词库
        if product_line == "nicotine_vape":
            channel_words = NICOTINE_VAPE_CHANNEL
            intent_words = NICOTINE_VAPE_INTENT
            supply_words = NICOTINE_VAPE_SUPPLY_CHAIN
        else:
            channel_words = CANNABIS_DEVICE_CHANNEL
            intent_words = CANNABIS_DEVICE_INTENT
            supply_words = CANNABIS_DEVICE_SUPPLY_CHAIN

        keywords = []

        # 过滤：排除含 manufacturer/factory/supplier 的词（搜到同行工厂）
        buyer_channel = [w for w in channel_words if "manufacturer" not in w and "factory" not in w and "supplier" not in w and "OEM" not in w and "ODM" not in w]
        if not buyer_channel:
            buyer_channel = channel_words
        # 1. 渠道词 + 城市/国家
        for cw in random.sample(buyer_channel, min(4, len(buyer_channel))):
            if city and random.random() > 0.5:
                keywords.append(f"{cw} {city}")
            else:
                keywords.append(f"{cw} {country_en}")

        # 2. 意向词 + 产品线
        for iw in random.sample(intent_words, min(2, len(intent_words))):
            keywords.append(f"{iw} vape {city or country_en}")

        # 3. 供应链词 — 按旧系统经验改：搜 ODM/OEM 的词会找到同行工厂
        # 排除 manufacturer/factory/supplier/OEM/ODM → 只搜买家侧
        buyer_words = [w for w in supply_words
                       if not any(kw in w.lower() for kw in ("manufacturer", "factory", "supplier", "oem", "odm"))]
        if not buyer_words:
            buyer_words = ["vape private label", "vape sourcing"]
        for sw in random.sample(buyer_words, min(2, len(buyer_words))):
            keywords.append(f"{sw} {country_en}")

        # 4. 本地语言关键词（如有，替换英语词）
        if country in MULTILANG_KEYWORDS:
            lang_kws = MULTILANG_KEYWORDS[country].get("distributor", [])
            keywords = random.sample(lang_kws, min(6, len(lang_kws)))
        else:
            # 去重
            seen = set()
            unique = []
            for kw in keywords:
                kl = kw.lower().strip()
                if kl and kl not in seen:
                    seen.add(kl)
                    unique.append(kw)
            keywords = unique

        random.shuffle(keywords)
        return keywords[:8] if len(keywords) >= 8 else keywords
