"""
三级验证管线 + 客户画像 — 计划 §4.2.3 + 旧 customer_signal.py 移植。
"""

import json, logging, re, requests
from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from .customer_signal import detect_customer_signal

logger = logging.getLogger("discovery.validation")

# AI 重试配置
def _call_ai(prompt: str, temperature: float = 0.1, max_tokens: int = 300, max_retries: int = 2) -> str:
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": DEEPSEEK_MODEL, "messages": [{"role":"user","content":prompt}],
                      "temperature": temperature, "max_tokens": max_tokens},
                timeout=30,
            )
            if resp.status_code == 200:
                msg = resp.json()["choices"][0]["message"]
                return (msg.get("content") or msg.get("reasoning_content") or "").strip()
            if resp.status_code == 429:
                import time; time.sleep((attempt+1)*10)
        except Exception:
            pass
    return ""


# ── L1: 数字足迹 ──────────────────────────────

def level1_digital_footprint(row: dict) -> tuple[bool, int, str]:
    score, reasons = 0, []
    website = row.get("官网","")
    if website.startswith("https://"): score+=10; reasons.append("HTTPS+10")
    elif website.startswith("http://"): score+=5; reasons.append("HTTP+5")
    email = row.get("Email","")
    if "@" in email and email.split("@")[-1].lower() not in {"gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com"}:
        score+=8; reasons.append("公司邮箱+8")
    social = sum(1 for f in ["Instagram","Facebook","LinkedIn","X","TikTok"] if row.get(f))
    if social>=2: score+=10; reasons.append(f"{social}社媒+10")
    elif social==1: score+=5
    phone = row.get("电话","")
    if len(str(phone))>=10: score+=5; reasons.append("电话+5")
    return score>=8, score, ";".join(reasons)


# ── L2: AI 深度判定 (增强版，移植旧 ai_judgment.py) ──

def level2_ai_judge(row: dict) -> tuple[bool, int, str, str]:
    """判定 B2B 商业主体。增强：5条件+6示例排除非商业页面。"""
    name = row.get("公司名","N/A")
    desc = (row.get("经营介绍") or "")[:300]
    web = row.get("官网","N/A")
    country = row.get("国家","")

    prompt = f"""你是B2B电子烟ODM工厂(DZAT)的客户开发专家。判断以下是否是一个有实际产品的公司/品牌官网——即你可能会向其推销ODM代工服务的潜在客户。

返回true必须满足全部条件:
1. 独立公司/品牌网站，有自己销售的产品线（电子烟/vape/CBD/大麻设备）
2. 是品牌商/批发商/分销商/进口商（不是制造商同行）
3. 不是信息类文章/博客/新闻/法规页
4. 不是测评/排行榜/对比类内容
5. 不是电商平台(Alibaba/Amazon)

公司: {name}
国家: {country}
描述: {desc[:300]}
网站: {web}

返回JSON: {{"is_business":true/false,"confidence":0-100,"business_type":"distributor/wholesaler/brand/retailer/manufacturer","evidence":"evidence in English","is_chinese_competitor":true/false}}"""

    resp = _call_ai(prompt, max_tokens=300)
    if not resp:
        return False, 0, "未知", "AI调用失败"
    try:
        r = json.loads(resp.replace("```json","").replace("```","").strip())
    except json.JSONDecodeError:
        m = re.search(r'\{[^{}]*\}', resp, re.DOTALL)
        r = json.loads(m.group()) if m else {"is_business": False}
    if r.get("is_chinese_competitor"):
        return False, 0, "中国同行", r.get("evidence","")
    return r.get("is_business",False), r.get("confidence",0), r.get("business_type",""), r.get("evidence","")


# ── L3: 金矿信号 + 客户画像 (增强版) ──────────

def level3_gold_signals(row: dict) -> list[str]:
    """金矿信号检测。"""
    text = f"{row.get('经营介绍','')} {row.get('深度报告','')} {row.get('备注','')}".lower()
    signals = []
    gold = {
        "招聘采购": ["hiring","recruiting","purchasing manager","supply chain"],
        "多品牌": ["multiple brands","smok","vaporesso","geekvape","elf bar"],
        "展会": ["exhibitor","expo","trade show","hall of vape","intertabac"],
        "多门店": ["serving \\d+ retail","stores across","chain of"],
        "找供应商": ["looking for supplier","seeking partner","sourcing new"],
        "品类扩张": ["new brands coming","expanding","new category"],
    }
    for name, pats in gold.items():
        if any(re.search(p, text) for p in pats):
            signals.append(name)
    return signals


def detect_portrait(row: dict) -> dict:
    """客户画像检测 — 移植旧 customer_signal.py。"""
    return detect_customer_signal(
        company_name=row.get("公司名",""),
        description=row.get("经营介绍",""),
        website_text=row.get("深度报告",""),
        founded_year=str(row.get("成立时间","")),
        country=row.get("国家",""),
        city=row.get("城市",""),
    )
