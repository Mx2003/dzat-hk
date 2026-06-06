#!/usr/bin/env python3
"""
EspoCRM 初始化脚本 — 自定义字段 + 实体 + 导入 leads.db

使用方法: 在服务器上运行
python3 /opt/dzat-b2b/setup_espocrm.py
"""

import json
import sqlite3
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API_BASE = "http://localhost:8080/api/v1"
API_KEY = "3f0f4ef281df645acdc6e30bf3d406ac"
HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json",
}


def api(method, path, data=None):
    """调用 EspoCRM API。"""
    url = f"{API_BASE}/{path}"
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=HEADERS, method=method)
    try:
        resp = urlopen(req)
        return json.loads(resp.read())
    except HTTPError as e:
        content = e.read().decode()[:300]
        print(f"  API error {e.code}: {content}")
        return None


def create_lead_fields():
    """在 Lead 实体上创建自定义字段。"""
    print("[Lead] Creating custom fields...")

    fields = [
        {"type": "varchar", "name": "sourceKeywords", "label": "来源关键词",
         "maxLength": 500, "isCustom": True},
        {"type": "enum", "name": "productLine", "label": "产品线",
         "options": ["nicotine_vape", "cannabis_device", "both"],
         "isCustom": True},
        {"type": "varchar", "name": "customerPortrait", "label": "客户画像",
         "maxLength": 200, "isCustom": True},
        {"type": "int", "name": "leadScore", "label": "评分",
         "isCustom": True},
        {"type": "enum", "name": "scoreGrade", "label": "评分等级",
         "options": ["S", "A", "B", "C"], "isCustom": True},
        {"type": "text", "name": "deepReport", "label": "深度报告",
         "isCustom": True},
        {"type": "varchar", "name": "devPriority", "label": "开发优先级",
         "maxLength": 50, "isCustom": True},
        {"type": "jsonObject", "name": "socialLinks", "label": "社媒链接JSON",
         "isCustom": True},
        {"type": "varchar", "name": "sourceUrl", "label": "来源链接",
         "maxLength": 500, "isCustom": True},
        {"type": "varchar", "name": "leadCountry", "label": "国家",
         "maxLength": 100, "isCustom": True},
        {"type": "varchar", "name": "leadCity", "label": "城市",
         "maxLength": 100, "isCustom": True},
    ]

    for field in fields:
        name = field["name"]
        result = api("POST", "EntityManager/createField/Lead", field)
        if result:
            print(f"  Created: {field['label']}")
        else:
            print(f"  Skipped (may exist): {field['label']}")


def create_contact_fields():
    """在 Contact 实体上创建社媒字段。"""
    print("\n[Contact] Creating social media fields...")

    platforms = [
        ("whatsapp", "WhatsApp"),
        ("linkedin", "LinkedIn"),
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("xHandle", "X/Twitter"),
        ("tiktok", "TikTok"),
    ]

    for name, label in platforms:
        api("POST", "EntityManager/createField/Contact", {
            "type": "varchar", "name": name, "label": label,
            "maxLength": 300, "isCustom": True,
        })
        print(f"  Created: {label}")


def create_outreach_entity():
    """创建触达记录自定义实体。"""
    print("\n[OutreachRecord] Creating entity...")

    # Create entity
    result = api("POST", "EntityManager/createEntity", {
        "name": "OutreachRecord",
        "label": "触达记录",
        "type": "Base",
        "isCustom": True,
    })
    if result:
        print("  Entity created: OutreachRecord")
    else:
        print("  Entity may already exist")

    # Create fields
    fields = [
        {"type": "varchar", "name": "outreachPlatform", "label": "平台",
         "maxLength": 50, "isCustom": True},
        {"type": "varchar", "name": "outreachAction", "label": "动作",
         "maxLength": 200, "isCustom": True},
        {"type": "enum", "name": "outreachStatus", "label": "状态",
         "options": ["已发送", "发送失败", "已回复", "跳过"],
         "isCustom": True},
        {"type": "datetime", "name": "sentTime", "label": "发送时间",
         "isCustom": True},
        {"type": "datetime", "name": "replyTime", "label": "回复时间",
         "isCustom": True},
        {"type": "text", "name": "outreachMessage", "label": "消息内容",
         "isCustom": True},
        {"type": "varchar", "name": "outreachLeadId", "label": "关联线索",
         "maxLength": 100, "isCustom": True},
    ]

    for field in fields:
        api("POST", "EntityManager/createField/OutreachRecord", field)
        print(f"  Created: {field['label']}")


def import_leads():
    """从本地 SQLite 导入现有 leads.db 到 EspoCRM。"""
    db_path = "/opt/dzat-b2b/../src/data/leads.db"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM leads ORDER BY 评分 DESC LIMIT 50").fetchall()

        imported = 0
        for row in rows:
            lead_data = {
                "name": row["公司名"] or "Unknown Company",
                "description": row["经营介绍"] or "",
                "website": row["官网"] or "",
                "emailAddress": row["Email"] or "",
                "phoneNumber": row["电话"] or "",
                "sourceKeywords": row["来源关键词"] or "",
                "leadCountry": row["国家"] or "",
                "leadCity": row["城市"] or "",
                "productLine": row["产品线"] or "",
                "customerPortrait": row["客户画像"] or "",
                "leadScore": int(row["评分"] or 0),
                "scoreGrade": row["评分等级"] or "",
                "sourceUrl": row["来源链接"] or "",
            }

            result = api("POST", "Lead", lead_data)
            if result:
                imported += 1
                if imported % 10 == 0:
                    print(f"  Imported {imported}/{len(rows)} leads")

        print(f"\n[Import] Done: {imported} leads imported")
        conn.close()
    except Exception as e:
        print(f"[Import] Error: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("DZAT B2B — EspoCRM Setup")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "import":
        import_leads()
    else:
        create_lead_fields()
        create_contact_fields()
        create_outreach_entity()
        print("\n[Done] Run 'python3 setup_espocrm.py import' to import leads")
