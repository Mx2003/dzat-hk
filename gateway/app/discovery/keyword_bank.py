"""
静态关键词库 — 从旧系统 keyword_bank.py + market_config.py 移植。

数据来源:
- 大麻设备名词汇总.docx
- 海外电子烟&合规大麻设备大型客户精准定位关键词库（纯海外大客户版）.docx

组织: 按产品线 × 类型（品类/渠道/供应链/意向）
"""

# ── 尼古丁电子烟 ────────────────────────────────

NICOTINE_VAPE_CHANNEL = [
    "vape distributor", "vape wholesaler", "vape wholesale",
    "e-cigarette distributor", "e-liquid distributor",
    "vape distribution", "master distributor",
    "authorized distributor", "exclusive distributor",
    "regional distributor", "national distributor",
    "vape shop", "vape store", "vape retail", "vape retailer",
    "vape store chain", "vape shop chain",
    "vape franchise", "vape outlet", "smoke shop", "tobacco shop",
    "vape importer", "e-cigarette importer",
    "vape dealer", "authorized dealer", "vape reseller",
    "vape stockist", "vape buyer", "vape procurement",
    "online vape store", "vape ecommerce", "vape dropshipping",
]

NICOTINE_VAPE_INTENT = [
    "looking for supplier", "seeking partner", "need wholesale",
    "request quote", "new launch", "expansion",
    "new category", "entering market", "business opportunity",
    "sourcing partner", "product line expansion",
]

NICOTINE_VAPE_SUPPLY_CHAIN = [
    "vape OEM", "vape ODM", "vape private label",
    "vape manufacturer", "vape factory", "vape supplier",
    "vape sourcing", "vape procurement",
]

# ── 大麻设备 ────────────────────────────────────

CANNABIS_DEVICE_CHANNEL = [
    "cannabis vape distributor", "CBD vape wholesaler",
    "THC vape distributor", "cannabis hardware distributor",
    "dab pen wholesaler", "510 cartridge distributor",
    "dry herb vaporizer dealer", "CBD shop",
    "cannabis dispensary", "THC vape retailer",
    "cannabis vape importer", "CBD vape stockist",
]

CANNABIS_DEVICE_INTENT = [
    "looking for supplier", "seeking OEM partner",
    "need cannabis hardware manufacturer", "private label CBD vape",
    "cannabis vape sourcing", "new product line CBD",
]

CANNABIS_DEVICE_SUPPLY_CHAIN = [
    "cannabis vape OEM", "cannabis vape ODM",
    "CBD vape manufacturer", "THC vape factory",
    "cannabis hardware supplier", "vape cartridge manufacturer",
]

# ── 高价值金矿信号词 ──────────────────────────────

HIDDEN_GEM_SIGNALS = {
    "seeking_supply": {
        "search_prefixes": [
            "looking for vape supplier", "seeking vape OEM",
            "need vape private label", "vape sourcing partner wanted",
        ],
    },
    "regional_emerging": {
        "search_prefixes": [
            "regional vape distributor", "local vape brand",
            "vape startup brand", "emerging vape market",
        ],
    },
    "traditional_crossover": {
        "search_prefixes": [
            "beauty retailer vape", "wellness brand vape",
            "tobacco shop e-cigarette", "pharmacy vape product",
        ],
    },
}

# ── 多语言关键词 ─────────────────────────────────

MULTILANG_KEYWORDS = {
    "德国": {
        "distributor": ["E-Zigarette Großhändler", "E-Zigaretten Distributor",
                        "Dampfer Shop", "E-Zigaretten Importeur"],
    },
    "法国": {
        "distributor": ["cigarette électronique distributeur", "vape grossiste",
                        "e-liquide importateur", "vapoteur boutique"],
    },
    "西班牙": {
        "distributor": ["cigarrillo electrónico distribuidor", "vapeador mayorista",
                        "tienda vapeo", "importador e-cigarrillo"],
    },
    "意大利": {
        "distributor": ["sigaretta elettronica distributore", "svapo grossista",
                        "negozio svapo", "importatore e-cig"],
    },
    "荷兰": {
        "distributor": ["e-sigaret groothandel", "vape distributeur",
                        "dampen winkel", "e-sigaret importeur"],
    },
    "日本": {
        "distributor": ["電子タバコ 卸売", "VAPE ディストリビューター",
                        "電子タバコ 輸入", "ベイプショップ"],
    },
    "巴西": {
        "distributor": ["cigarro eletrônico distribuidor", "vape atacadista",
                        "loja vape", "importador e-cigarro"],
    },
}

# ── 目标市场（15 国 × 城市 × 法律类别）───────────

# 中文→英文国名
CN_TO_EN = {"美国":"USA","德国":"Germany","英国":"UK","加拿大":"Canada","荷兰":"Netherlands",
            "法国":"France","意大利":"Italy","西班牙":"Spain","澳大利亚":"Australia",
            "日本":"Japan","韩国":"South Korea","阿联酋":"UAE","巴西":"Brazil","南非":"South Africa",
            "墨西哥":"Mexico","泰国":"Thailand"}

TARGET_MARKETS = {
    "美国": {"priority": "P0", "cities": ["Los Angeles", "Miami", "Houston", "Chicago", "New York"],
             "legal": ["nicotine_vape", "cannabis_device"], "lang": "en"},
    "德国": {"priority": "P0", "cities": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
             "legal": ["nicotine_vape", "cannabis_device"], "lang": "de"},
    "英国": {"priority": "P0", "cities": ["London", "Manchester", "Birmingham", "Glasgow"],
             "legal": ["nicotine_vape"], "lang": "en"},
    "加拿大": {"priority": "P0", "cities": ["Toronto", "Vancouver", "Montreal", "Calgary"],
               "legal": ["nicotine_vape", "cannabis_device"], "lang": "en"},
    "荷兰": {"priority": "P0", "cities": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
             "legal": ["nicotine_vape", "cannabis_device"], "lang": "nl"},
    "法国": {"priority": "P1", "cities": ["Paris", "Lyon", "Marseille", "Toulouse"],
             "legal": ["nicotine_vape"], "lang": "fr"},
    "意大利": {"priority": "P1", "cities": ["Rome", "Milan", "Naples", "Turin"],
               "legal": ["nicotine_vape"], "lang": "it"},
    "西班牙": {"priority": "P1", "cities": ["Madrid", "Barcelona", "Valencia", "Seville"],
               "legal": ["nicotine_vape"], "lang": "es"},
    "澳大利亚": {"priority": "P1", "cities": ["Sydney", "Melbourne", "Brisbane", "Perth"],
                 "legal": ["nicotine_vape"], "lang": "en"},
    "日本": {"priority": "P1", "cities": ["Tokyo", "Osaka", "Nagoya", "Fukuoka"],
             "legal": ["nicotine_vape"], "lang": "ja"},
    "韩国": {"priority": "P1", "cities": ["Seoul", "Busan", "Incheon", "Daegu"],
             "legal": ["nicotine_vape"], "lang": "ko"},
    "阿联酋": {"priority": "P1", "cities": ["Dubai", "Abu Dhabi", "Sharjah"],
               "legal": ["nicotine_vape"], "lang": "ar"},
    "巴西": {"priority": "P2", "cities": ["Sao Paulo", "Rio de Janeiro", "Brasilia"],
             "legal": ["nicotine_vape"], "lang": "pt"},
    "南非": {"priority": "P2", "cities": ["Johannesburg", "Cape Town", "Durban"],
             "legal": ["nicotine_vape"], "lang": "en"},
    "墨西哥": {"priority": "P2", "cities": ["Mexico City", "Guadalajara", "Monterrey"],
               "legal": ["nicotine_vape"], "lang": "es"},
    "泰国": {"priority": "P2", "cities": ["Bangkok", "Chiang Mai", "Phuket"],
             "legal": ["cannabis_device"], "lang": "th"},
}
