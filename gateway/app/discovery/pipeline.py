"""
获客编排器 — Strategy Agent → 搜索 → 验证 → 评分 → EspoCRM。

计划 §4.2.4 执行图：并行搜索 → 三级验证 → 入库。
"""

import logging
from typing import Any, Optional
import requests

from .strategy import StrategyAgent
from .search_agents import google_search
from .validation import level1_digital_footprint, level2_ai_judge, level3_gold_signals
from .scoring import score_text, grade_score, detect_product_line, detect_customer_type, CUSTOMER_PORTRAIT_WEIGHTS
from ..config import ESPOCRM_URL, ESPOCRM_API_KEY

logger = logging.getLogger("discovery.pipeline")

# 运行历史
_run_history: list[dict] = []


class DiscoveryPipeline:
    """获客编排器。"""

    def __init__(self):
        self._strategy = StrategyAgent()
        self._espocrm = f"{ESPOCRM_URL}/api/v1"
        self._esh = {"X-Api-Key": ESPOCRM_API_KEY, "Content-Type": "application/json"}

    def run_round(self) -> dict:
        """执行一轮获客：策略决策 → 搜索 → 验证 → 入库。"""
        global _run_history

        # 1. Strategy Agent 决策
        decision = self._strategy.decide(_run_history, sum(h.get("leads", 0) for h in _run_history[-3:]))
        if decision.get("strategy_key") == "STOP":
            logger.info("[Pipeline] Strategy says STOP — markets exhausted")
            return {"status": "stopped", "reason": "连续零产出"}

        market = decision.get("market", {})
        country = market.get("country", "德国")
        city = market.get("city", "Berlin")
        keywords = decision.get("keywords", ["vape distributor"])
        keyword = keywords[0]

        logger.info(f"[Pipeline] round: {country}/{city} — {keyword}")

        # 2. Google 搜索
        google_rows = google_search(keyword, country, limit=5)

        # 3. 验证 + 评分 + 入库
        total_new = 0
        for row in google_rows:
            row["国家"] = row.get("国家", country)
            row["城市"] = row.get("城市", city)
            row["产品线"] = detect_product_line(f"{row.get('公司名','')} {row.get('经营介绍','')}")

            # 评分
            text = f"{row.get('公司名','')} {row.get('经营介绍','')} {row.get('来源关键词','')}"
            score, hits, penalties = score_text(text)
            if row.get("官网", "").startswith("http"):
                score += 10
            row["评分"] = max(5, min(100, score))
            row["评分等级"] = grade_score(row["评分"])
            row["命中关键词"] = ";".join(hits) if hits else ""
            row["客户类型"] = detect_customer_type(text)

            # L1 + L2
            l1_ok, l1_score, l1_reason = level1_digital_footprint(row)
            row["命中信号"] = f"L1:{l1_reason}" if l1_reason else ""

            if l1_ok or row["评分"] >= 30:
                l2_ok, conf, biz_type, evidence = level2_ai_judge(row)
                row["置信度"] = conf
                row["命中信号"] += f";L2:{biz_type}" if biz_type else ""

            # 入库 EspoCRM
            lead_id = self._upsert_lead(row)
            if lead_id:
                total_new += 1

        # 4. 记录历史
        _run_history.append({
            "market": country, "city": city,
            "strategy": decision.get("strategy_key", ""),
            "leads": total_new,
        })

        logger.info(f"[Pipeline] round done: {total_new} new leads")
        return {"status": "ok", "new_leads": total_new, "country": country, "keyword": keyword}

    def _upsert_lead(self, row: dict) -> Optional[str]:
        """创建 Lead 到 EspoCRM。"""
        try:
            # 电话清洗：非 E.164 格式就跳过（不存比存错的强）
            raw_phone = (row.get("电话") or "").strip()
            digits = "".join(c for c in raw_phone if c.isdigit())
            clean_phone = f"+{digits}" if 7 <= len(digits) <= 15 else ""

            payload = {
                "firstName": (row.get("公司名", "Unknown"))[:50],
                "lastName": "",
                "website": row.get("官网", ""),
                "emailAddress": row.get("Email", ""),
                "phoneNumber": clean_phone,
                "description": row.get("经营介绍", ""),
                "addressCountry": row.get("国家", ""),
                "addressCity": row.get("城市", ""),
                "cSourceKeywords": row.get("来源关键词", ""),
                "cProductLine": row.get("产品线", ""),
                "cSourceUrl": row.get("来源链接", ""),
                "cLeadScore": str(row.get("评分", 0)),
                "cScoreGrade": row.get("评分等级", ""),
                "cLinkedin": row.get("LinkedIn", ""),
                "cInstagram": row.get("Instagram", ""),
                "cFacebook": row.get("Facebook", ""),
                "cXHandle": row.get("X", ""),
            }
            resp = requests.post(
                f"{self._espocrm}/Lead",
                headers=self._esh, json=payload, timeout=10,
            )
            if resp.status_code in (200, 201, 409):
                data = resp.json()
                id_ = None
                if isinstance(data, dict): id_ = data.get("id")
                if isinstance(data, list) and data: id_ = data[0].get("id")
                if id_: return id_
                logger.warning(f"[Pipeline] Upsert no ID in response: {str(data)[:200]}")
            else:
                logger.warning(f"[Pipeline] Upsert HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"[Pipeline] EspoCRM error: {e.__class__.__name__} {e}")
        return None
