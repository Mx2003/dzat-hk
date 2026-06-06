"""
客户画像信号检测引擎 — 从旧 customer_signal.py 移植到 Ubuntu 服务器。

四种画像: seeking_supply / regional_emerging / new_brand_2yr / traditional_crossover
"""

# 区域新兴品牌
REGIONAL_EMERGING_SIGNALS = [
    "regional brand", "local brand", "city brand", "state brand",
    "based in", "proudly", "locally owned", "family owned",
    "indie brand", "independent brand", "boutique brand",
    "small batch", "artisan", "craft", "handcrafted",
    "specialty", "niche brand", "curated",
    "growing", "emerging", "up and coming", "rising",
    "upcoming brand", "fastest growing",
]

# 正在找供应链（价值最高）
SEEKING_SUPPLY_SIGNALS = [
    "looking for supplier", "seeking supplier", "need supplier",
    "looking for manufacturer", "seeking manufacturer", "need manufacturer",
    "looking for OEM", "looking for ODM", "OEM partner",
    "seeking partner", "looking for partner", "partnership opportunity",
    "sourcing", "procurement", "need wholesale", "wholesale needed",
    "looking for wholesale", "buying", "purchasing",
    "request for quote", "RFQ", "request quote",
    "private label wanted", "private label needed",
    "custom brand", "custom vape", "own brand", "white label",
    "import", "importing", "importer looking",
    "direct from factory", "factory direct needed",
]

# 近2年新品牌
NEW_BRAND_SIGNALS = [
    "founded 2023", "founded 2024", "founded 2025", "founded 2026",
    "established 2023", "established 2024", "established 2025", "established 2026",
    "since 2023", "since 2024", "since 2025",
    "brand new", "new brand", "newly founded",
    "just launched", "recently launched",
    "new company", "startup", "start-up",
    "new venture", "new business", "new to market",
    "first product", "debut", "launching soon",
    "early stage", "incubator", "accelerator",
]

# 传统跨界进入
TRADITIONAL_CROSSOVER_SIGNALS = [
    "expanding into", "entering market", "new category",
    "new product line", "new division", "diversifying",
    "expansion", "new vertical", "new market", "branching out",
    "tobacco company", "tobacco brand", "cigarette brand",
    "beauty brand", "cosmetics company", "skincare brand",
    "wellness company", "health brand", "supplement brand",
    "pharmacy chain", "drugstore", "drug store",
    "convenience chain", "convenience store", "gas station chain",
    "retail chain", "department store",
    "lifestyle brand", "fashion brand", "luxury brand",
    "beverage company", "food company", "snack brand",
    "parent company", "subsidiary of", "spin-off",
]

PORTRAIT_WEIGHTS = {"seeking_supply": 15, "traditional_crossover": 12, "regional_emerging": 8, "new_brand_2yr": 5}


def detect_customer_signal(company_name: str = "", description: str = "",
                           website_text: str = "", founded_year: str = "",
                           city: str = "", country: str = "", followers: int = 0) -> dict:
    """检测四种客户画像信号。返回最佳匹配画像和权重。"""
    text = f"{company_name} {description} {website_text}".lower()

    results = []
    for name, signals, weight in [
        ("seeking_supply", SEEKING_SUPPLY_SIGNALS, 15),
        ("traditional_crossover", TRADITIONAL_CROSSOVER_SIGNALS, 12),
        ("regional_emerging", REGIONAL_EMERGING_SIGNALS, 8),
        ("new_brand_2yr", NEW_BRAND_SIGNALS, 5),
    ]:
        matched = [s for s in signals if s in text]
        conf = min(100, len(matched) * 12 + (10 if followers and 500 <= int(followers) <= 50000 else 0))
        if matched:
            results.append({"portrait": name, "signals": matched, "confidence": conf, "weight": weight})

    results.sort(key=lambda r: (r["weight"], r["confidence"]), reverse=True)
    primary = results[0]["portrait"] if results else "none"
    bonus = results[0]["weight"] if results else 0

    return {"primary_portrait": primary, "all_portraits": results, "bonus_score": bonus,
            "signals_summary": "|".join(f"{r['portrait']}({r['confidence']}%)" for r in results) if results else ""}
