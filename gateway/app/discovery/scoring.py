"""
关键词权重 & 评分引擎。

计划 §4.2：不是一条 AI 判定生死，而是多层信号叠加。
"""

# 关键词权重（从旧 config.py 和 keyword_bank.py 提取）
KEYWORD_WEIGHTS = {
    "OEM": 12, "ODM": 12, "private label": 12,
    "supplier": 10, "manufacturer": 10,
    "looking for supplier": 12, "seeking partner": 12,
    "need wholesale": 12, "request quote": 12,
    "distributor": 8, "wholesaler": 8, "retailer": 6,
    "vape shop": 8, "smoke shop": 8,
    "regional brand": 9, "importer": 7,
    "sourcing": 8, "procurement": 8,
    "expansion": 8, "new category": 10, "entering market": 10,
    "beauty": 6, "cosmetics": 6, "wellness": 6,
    "lifestyle": 5, "health": 4, "organic": 4,
    "cannabis device": 10, "dry herb vaporizer": 10,
    "extract vaporizer": 10,
    "coil": 3, "battery": 2, "atomizer": 3,
    # 中国同行扣分
    "china factory": -20, "china manufacturer": -20, "china oem": -20,
    "made in china": -20, "shenzhen factory": -25,
    "alibaba.com": -15, "made-in-china.com": -15,
    # 非商业扣分
    "repair": -10, "tutorial": -12, "review": -8, "blog": -8,
    "personal use": -15, "hobby": -12, "counterfeit": -20,
}

SCORE_THRESHOLDS = {"S": 85, "A": 65, "B": 45, "C": 0}
CUSTOMER_PORTRAIT_WEIGHTS = {"seeking_supply": 15, "traditional_crossover": 12, "regional_emerging": 8, "new_brand_2yr": 5}


def score_text(text: str) -> tuple[int, list[str], list[str]]:
    """对文本打分，返回 (分数, 命中词, 扣分词)。"""
    lowered = text.lower()
    score, hits, penalties = 20, [], []

    for kw, weight in KEYWORD_WEIGHTS.items():
        if kw.lower() in lowered:
            if weight >= 0:
                score += weight
                hits.append(kw)
            else:
                score += weight
                penalties.append(kw)

    return max(0, min(100, score)), hits, penalties


def grade_score(score: int) -> str:
    for grade, threshold in SCORE_THRESHOLDS.items():
        if score >= threshold:
            return grade
    return "C"


# ── 产品线信号词 (移植旧 market_config.py) ──

NICOTINE_VAPE_SIGNALS = [
    "nicotine", "nic salt", "nicotine salt", "freebase nicotine",
    "e-liquid", "e-juice", "vape juice", "pg/vg",
    "disposable vape", "disposable pod", "closed pod system",
    "refillable pod", "open pod", "MTL vape", "mouth to lung",
    "sub-ohm tank", "vape mod", "box mod", "pod mod",
]

CANNABIS_DEVICE_SIGNALS = [
    "cannabis", "thc", "cbd", "delta 8", "delta 9", "delta 10",
    "thc-o", "hxc", "live resin", "rosin", "shatter", "wax",
    "dab", "dabbing", "dab rig", "concentrate", "extract",
    "dry herb", "hemp", "marijuana", "420",
    "ceramic coil", "quartz coil", "510 thread", "cartridge",
    "cannabis hardware", "cannabis accessory",
]


def detect_product_line(text: str) -> tuple[str, int]:
    """两层判定：术语命中统计 → 分类。返回 (产品线, 置信度)。"""
    t = text.lower()
    nic = [s for s in NICOTINE_VAPE_SIGNALS if s in t]
    can = [s for s in CANNABIS_DEVICE_SIGNALS if s in t]
    nc, cc = len(nic), len(can)

    if nc == 0 and cc == 0:
        return ("unknown", 0)
    if nc >= 3 and cc == 0:
        return ("nicotine_vape", min(95, 50 + nc * 10))
    if cc >= 3 and nc == 0:
        return ("cannabis_device", min(95, 50 + cc * 10))
    if nc >= 3 and cc >= 3:
        return ("both", min(90, 60 + (nc + cc) * 5))
    if nc > cc:
        return ("nicotine_vape", min(85, 40 + nc * 5))
    if cc > nc:
        return ("cannabis_device", min(85, 40 + cc * 5))
    return ("nicotine_vape", 20)


def detect_customer_type(text: str) -> str:
    """检测客户类型。"""
    t = text.lower()
    if any(kw in t for kw in ["wholesale", "distributor", "distribution", "b2b"]):
        return "批发商/分销商"
    if any(kw in t for kw in ["manufacturer", "oem", "odm", "factory"]):
        return "制造商/OEM"
    if any(kw in t for kw in ["brand", "label"]):
        return "品牌商"
    if any(kw in t for kw in ["retail", "shop", "store", "vape shop"]):
        return "零售商"
    return "未知"
