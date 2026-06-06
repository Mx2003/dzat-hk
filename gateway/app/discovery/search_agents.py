"""
搜索 Agent — 计划 §4.2.4 + Playwright CDP 驱动（移植旧 Windows 系统实现）

Google → Playwright locator 解析（同旧系统）
LinkedIn → 待 Chrome Pool 登录态
Social → 待 Chrome Pool 登录态
CrossEngine → HTTP (不需要浏览器)
"""

import re, logging, requests
from typing import Any
from urllib.parse import quote, urlparse

logger = logging.getLogger("discovery.search")

UNSUPPORTED_MSG = "pending Chrome Pool login"
INVALID_DOMAINS = {".edu", ".gov", ".mil", ".cn"}
SKIP_DOMAINS = {"google.com", "youtube.com", "facebook.com/login", "wikipedia.org", "linkedin.com/login",
                "outlook", "live.com", "microsoft", "accounts.google.com",
                "signin", "login.", "webmail", "consent.", "cookie.", "oath.",
                "gstatic", "googleapis", "doubleclick", "googletagmanager"}
_crawled_domains: set[str] = set()
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ── Google Search (Playwright CDP — 移植旧系统) ──

def google_search(keywords: list[str], country: str = "", limit: int = 3) -> list[dict]:
    if isinstance(keywords, str):
        keywords = [keywords]
    results = []
    from .chrome_pool import get_page
    from .anti_detection import random_delay

    for kw in keywords[:2]:
        if len(results) >= limit:
            break
        query = f"{kw} {country}"
        page = get_page()
        try:
            page.goto(f"https://www.google.com/search?q={quote(query)}&num=8&hl=en",
                      wait_until="domcontentloaded", timeout=20000)
            random_delay(2, 4)

            # Debug: check what Google returned
            page_title = page.title()
            body_text = page.locator("body").inner_text()[:300]
            logger.info(f"[Google] title='{page_title[:60]}' text='{body_text[:120]}'")

            divs = page.locator("div.g, div.yuRUbf, div.MjjYud, a[jsname], h3").all()
            logger.info(f"[Google] {len(divs)} result divs for '{kw[:30]}'")

            for div in divs[:6]:
                try:
                    if div.locator("h3").count() == 0:
                        continue
                    url = div.locator("a").first.get_attribute("href") or ""
                    if not url.startswith("http"):
                        continue
                    domain = urlparse(url).netloc.lower()
                    if domain in _crawled_domains:
                        continue
                    if any(domain.endswith(s) for s in INVALID_DOMAINS):
                        continue
                    if any(kw in url.lower() for kw in SKIP_DOMAINS):
                        continue

                    # Visit site via CDP
                    _crawled_domains.add(domain)
                    site_html = _fetch_site(page, url)
                    row = _parse(site_html, url, kw, country) if site_html else None
                    if row and row.get("公司名"):
                        results.append(row)
                        if len(results) >= limit:
                            return results
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[Google] {e}")
        finally:
            page.close()
    return results


def _fetch_site(page, url: str, timeout: int = 12) -> str | None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        page.wait_for_timeout(1500)
        return page.content()
    except Exception:
        return None


# ── LinkedIn (stub) ──────────────────────────────

def linkedin_search(keywords: list[str], country: str = "", limit: int = 3) -> list[dict]:
    return []


# ── Social (stub) ────────────────────────────────

def social_search(keywords: list[str], country: str = "", platforms=None) -> list[dict]:
    return []


# ── CrossEngine (HTTP) ──────────────────────────

def cross_engine_search(keywords: list[str], country: str = "", limit: int = 3) -> list[dict]:
    if isinstance(keywords, str):
        keywords = [keywords]
    results = []
    for kw in keywords[:3]:
        if len(results) >= limit:
            break
        for engine, tpl in [("Bing", "https://www.bing.com/search?q={q}&count=5"),
                              ("Yahoo", "https://search.yahoo.com/search?p={q}&n=5")]:
            try:
                url = tpl.format(q=quote(f"{kw} {country}"))
                resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
                if resp.status_code != 200:
                    continue
                raw_urls = re.findall(r'https?://[^\s"\'<>]{5,80}', resp.text)
                skip = {"bing.com", "yahoo.com", "microsoft.com", "google.com"}
                seen_s = set()
                for u in raw_urls:
                    domain = urlparse(u).netloc.lower()
                    if domain in seen_s or domain in _crawled_domains or any(d in domain for d in skip):
                        continue
                    if any(domain.endswith(s) for s in INVALID_DOMAINS):
                        continue
                    if any(kw in u.lower() for kw in SKIP_DOMAINS):
                        continue
                    seen_s.add(domain)
                    _crawled_domains.add(domain)
                    row = _simple_fetch(u, kw, country)
                    if row and row.get("公司名"):
                        results.append(row)
                        if len(results) >= limit:
                            return results
            except Exception as e:
                logger.warning(f"[{engine}] {e}")
    return results


# ── HTML 解析 ───────────────────────────────────

def _parse(html: str, url: str, keyword: str, country: str):
    if not html:
        return None

    # 公司名
    company = ""
    m = re.search(r'og:site_name["\s]+content="([^"]{2,60})"', html, re.I)
    if m: company = m.group(1).strip()
    if not company:
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            company = re.split(r'\s*[\|\-–]\s*', title)[0].strip()[:60]
    if not company:
        company = url.split("//")[-1].split("/")[0][:40]

    # 描述
    desc = ""
    m = re.search(r'name="description"[^>]*content="([^"]{10,})"', html, re.I)
    if m: desc = m.group(1).strip()[:200]

    # 联系方式 — 使用移植的 4 层提取
    from .contact_extraction import extract_all_contacts
    contacts = extract_all_contacts(html)

    # 过滤占位符
    email = contacts.get("email", "")
    phone = contacts.get("phone", "")
    if email and _is_placeholder("email", email): email = ""
    if phone and _is_placeholder("phone", phone): phone = ""

    # 检测国家
    domain = urlparse(url).netloc.lower()
    detected_country = _detect_country(html, domain, country)

    return {
        "公司名": company, "经营介绍": desc, "官网": url,
        "Email": email, "电话": phone,
        "WhatsApp": contacts.get("whatsapp", ""),
        "Instagram": contacts.get("instagram", ""),
        "Facebook": contacts.get("facebook", ""),
        "LinkedIn": contacts.get("linkedin", ""),
        "X": contacts.get("x", ""),
        "来源关键词": keyword, "国家": detected_country, "来源链接": url, "数据来源": "Search",
    }


# ── AI 预判（移植旧 collectors_google_search.py）──

def _ai_prescreen(results_data: list[dict]) -> list[int]:
    """AI 批量预判搜索结果——只返回可能是 B2B 客户的索引。"""
    if not results_data or len(results_data) <= 3:
        return list(range(len(results_data)))

    batch = ""
    for i, r in enumerate(results_data):
        batch += f"[{i}] {r.get('title','')[:80]} | {r.get('domain','')} | {r.get('snippet','')[:120]}\n"

    prompt = (
        "你是 B2B 电子烟/大麻设备 ODM 工厂的客户开发专家。"
        "快速扫一遍搜索结果，标记哪些像是「潜在客户公司网站」。\n"
        "潜在客户 = 电子烟/大麻设备品牌商、批发商、分销商、进口商。\n"
        "NOT = 新闻媒体、博客、论坛、政府、教育、个人页面、中国工厂。\n"
        "返回 JSON 数组，只包含可能是潜在客户的索引号。只返回 JSON。\n\n"
        f"{batch}"
    )
    try:
        from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_FLASH_MODEL
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model": DEEPSEEK_FLASH_MODEL, "temperature": 0.1,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=15,
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            import json
            try:
                indices = json.loads(raw.replace("```json","").replace("```",""))
                if isinstance(indices, list):
                    return [i for i in indices if 0 <= i < len(results_data)]
            except Exception:
                pass
    except Exception:
        pass
    return list(range(len(results_data)))


# ── 占位符过滤（移植旧 collectors_google_search.py）──

_PLACEHOLDER_EMAILS = {'your@email.com','test@test.com','example@example.com','email@example.com',
                       'user@example.com','info@example.com','admin@example.com','hello@example.com',
                       'mail@example.com','contact@example.com','support@example.com','sales@example.com',
                       'you@example.com','me@example.com','name@email.com','email@email.com',
                       'no-reply@example.com','noreply@example.com'}

_PLACEHOLDER_PHONE_PREFIXES = {'123-456','123456','555-000','555000','000-000','000000','(555)','(000)'}

def _is_placeholder(field: str, value: str) -> bool:
    v = value.lower().strip()
    if not v: return True
    if 'email' in field and v in _PLACEHOLDER_EMAILS: return True
    if any(p in v for p in ('your@','test@','example@','placeholder')): return True
    if 'phone' in field:
        if any(v.startswith(p) for p in _PLACEHOLDER_PHONE_PREFIXES): return True
        if set(v.replace('-','').replace(' ','')) == {'0'}: return True
    return False


# ── 国家/城市检测（移植旧 collectors_google_search.py）──

_COUNTRY_MAP = {"united states":"美国","germany":"德国","france":"法国","italy":"意大利",
    "spain":"西班牙","netherlands":"荷兰","japan":"日本","south korea":"韩国",
    "uae":"阿联酋","brazil":"巴西","mexico":"墨西哥","australia":"澳大利亚",
    "canada":"加拿大","united kingdom":"英国","uk":"英国","india":"印度"}

def _detect_country(html: str, domain: str = "", default: str = "") -> str:
    # JSON-LD
    m = re.search(r'"addressCountry"\s*:\s*"([^"]+)"', html, re.I)
    if m: return _COUNTRY_MAP.get(m.group(1).lower(), m.group(1))
    # og:country-name
    m = re.search(r'og:country-name"[^>]*content="([^"]+)"', html, re.I)
    if m: return _COUNTRY_MAP.get(m.group(1).lower(), m.group(1))
    # TLD
    tld_map = {".de":"德国",".fr":"法国",".it":"意大利",".es":"西班牙",".nl":"荷兰",
               ".jp":"日本",".kr":"韩国",".ae":"阿联酋",".br":"巴西",".mx":"墨西哥",
               ".au":"澳大利亚",".ca":"加拿大",".uk":"英国",".in":"印度"}
    for tld, cn in tld_map.items():
        if domain.endswith(tld): return cn
    return default


def _simple_fetch(url: str, keyword: str, country: str):
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=10, allow_redirects=True)
        return _parse(resp.text, url, keyword, country) if resp.status_code == 200 else None
    except Exception:
        return None
