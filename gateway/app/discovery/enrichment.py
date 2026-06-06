"""
官网爬取 + 联系方式提取。

计划 §4.2：Enrichment Pipeline（browser-use 子Agent, max_steps=5）。
当前版本：HTTP 快速爬取；Chrome Pool 上线后升级为 browser-use Agent。
"""

import re
import logging
from typing import Any
from urllib.parse import urlparse
import requests

logger = logging.getLogger("discovery.enrichment")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def enrich_lead(row: dict[str, Any]) -> dict[str, Any]:
    """爬取官网，补充联系方式。"""
    website = row.get("官网", "")
    if not website or not website.startswith("http"):
        return row

    try:
        resp = requests.get(website, headers={"User-Agent": UA}, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return row
        html = resp.text

        # 公司名补充
        if not row.get("公司名"):
            m = re.search(r'og:site_name["\s]+content="([^"]{2,60})"', html, re.I)
            row["公司名"] = m.group(1).strip() if m else ""

        # 邮箱补充
        if not row.get("Email"):
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
            bad = {"example.com", "domain.com", "test.com", "email.com"}
            for e in emails:
                if e.lower().split("@")[-1] not in bad and "noreply" not in e.lower():
                    row["Email"] = e
                    break

        # 电话补充
        if not row.get("电话"):
            phones = re.findall(r'\+\d{1,3}[\s\-.]?\d{1,4}[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}', html)
            if phones:
                row["电话"] = phones[0]

        # 社媒补充
        social_map = {
            "Instagram": r'instagram\.com/([a-zA-Z0-9._]+)',
            "Facebook": r'facebook\.com/([a-zA-Z0-9.]+)',
            "LinkedIn": r'linkedin\.com/company/([a-zA-Z0-9\-]+)',
            "X": r'(?:twitter|x)\.com/([a-zA-Z0-9_]+)',
        }
        for platform, pattern in social_map.items():
            if not row.get(platform):
                m = re.search(pattern, html, re.I)
                if m:
                    row[platform] = f"https://{platform.lower()}.com/{m.group(1)}"

    except Exception as e:
        logger.debug(f"[Enrich] {website[:40]}: {e}")

    return row
