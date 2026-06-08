"""VPS 看板 — HTML/SVG 图表 + Playwright 截图 → 企微图片推送"""
import base64
import hashlib
from datetime import datetime, timedelta
import requests
from .config import ESPOCRM_URL, ESPOCRM_API_KEY, WECHAT_WEBHOOK_URL


def _pct(part, total):
    if not total:
        return "0%"
    return f"{round(part / total * 100)}%"


def _fetch_leads(max_size: int = 500) -> list[dict]:
    """从 EspoCRM 拉取全量 Lead 数据"""
    h = {"X-Api-Key": ESPOCRM_API_KEY}
    all_leads = []
    offset = 0
    while True:
        r = requests.get(
            f"{ESPOCRM_URL}/api/v1/Lead",
            params={"maxSize": 100, "offset": offset, "sortBy": "createdAt", "desc": "true"},
            headers=h, timeout=15,
        )
        if r.status_code != 200:
            break
        data = r.json()
        batch = data.get("list", [])
        all_leads.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
        if len(all_leads) >= max_size:
            break
    return all_leads


def _svg_bar(values: list[dict], title: str, width: int = 420, height: int = 200) -> str:
    max_v = max((v["value"] for v in values), default=1)
    bar_h = max(20, min(32, (height - 40) // len(values) - 4))
    h = len(values) * (bar_h + 6) + 50
    bars = ""
    y = 32
    for v in values:
        w = int(v["value"] / max(max_v, 1) * (width - 160))
        color = v.get("color", "#4F8EF7")
        label = v.get("label", "")
        pct_text = v.get("pct", "")
        bars += f"""
        <text x="0" y="{y + bar_h - 8}" fill="#8899aa" font-size="11">{label}</text>
        <rect x="80" y="{y}" width="{max(w, 2)}" height="{bar_h}" rx="4" fill="{color}" opacity="0.85"/>
        <text x="{80 + w + 4}" y="{y + bar_h - 8}" fill="{color}" font-size="11" font-weight="600">{v["value"]} {pct_text}</text>
        """
        y += bar_h + 6
    return f"""<svg width="{width}" height="{h}" xmlns="http://www.w3.org/2000/svg">
        <text x="0" y="16" fill="#334" font-size="13" font-weight="700">{title}</text>
        {bars}
    </svg>"""


def _svg_kpi(label: str, value: str, sub: str, color: str,
             x: int = 0, y: int = 0, w: int = 130, h: int = 70) -> str:
    return f"""
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" opacity="0.08"/>
    <rect x="{x}" y="{y}" width="3" height="{h}" rx="1.5" fill="{color}"/>
    <text x="{x+14}" y="{y+22}" fill="#667" font-size="10">{label}</text>
    <text x="{x+14}" y="{y+44}" fill="{color}" font-size="20" font-weight="800">{value}</text>
    <text x="{x+14}" y="{y+58}" fill="#99a" font-size="9">{sub}</text>
    """


def build_html(leads: list[dict]) -> str:
    now = datetime.now()
    total = len(leads)

    score_dist = {"S": 0, "A": 0, "B": 0, "C": 0}
    for l in leads:
        g = l.get("scoreGrade") or "C"
        score_dist[g] = score_dist.get(g, 0) + 1

    platforms = {
        "li": ("LinkedIn", "cLiDmStatus", "cLinkedin", "#0077B5"),
        "ig": ("Instagram", "cIgDmStatus", "cInstagram", "#E4405F"),
        "fb": ("Facebook", "cFbDmStatus", "cFacebook", "#1877F2"),
        "wa": ("WhatsApp", "cWaDmStatus", "cWhatsapp", "#25D366"),
        "em": ("Email", "cEmDmStatus", "emailAddress", "#EA4335"),
        "x": ("X", "cXDmStatus", "cXHandle", "#1DA1F2"),
        "tk": ("TikTok", "cTkDmStatus", "cTiktok", "#FF0050"),
    }
    plat_stats = {}
    sent_total = 0
    for key, (label, status_f, has_f, color) in platforms.items():
        ok = sum(1 for l in leads if l.get(status_f) == "已发送")
        has = sum(1 for l in leads if l.get(has_f))
        plat_stats[key] = {"ok": ok, "has": has, "label": label, "color": color}
        sent_total += ok
    plat_sent_unique = set()
    for l in leads:
        for key, (label, status_f, has_f, color) in platforms.items():
            if l.get(status_f) == "已发送":
                plat_sent_unique.add(l.get("id"))
    sent_unique_count = len(plat_sent_unique)

    reply_fields = {"li": "cLiReply", "ig": "cIgReply", "fb": "cFbReply",
                    "wa": "cWaReply", "em": "cEmReply", "x": "cXReply", "tk": "cTkReply"}
    reply_total = sum(1 for l in leads if any(l.get(f) == "已回复" for f in reply_fields.values()))

    cutoff = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    h24_new = sum(1 for l in leads if (l.get("createdAt") or "") >= cutoff)
    h24_sent = 0
    h24_reply = sum(1 for l in leads if (l.get("cLastReply") or "") >= cutoff)

    wa_chats = sum(1 for l in leads if l.get("cWaChatStatus") in ("聊天中", "已完成"))
    wa_hot = sum(1 for l in leads if l.get("cWaIntent") == "高")
    wa_done = sum(1 for l in leads if l.get("cWaChatStatus") == "已完成")
    wa_msgs = sum(int(l.get("cWaMsgCount") or 0) for l in leads)

    kpis = _svg_kpi("总线索", str(total), f"S:{score_dist['S']} A:{score_dist['A']} B:{score_dist['B']}", "#4F8EF7", 0, 0)
    kpis += _svg_kpi("已触达", str(sent_unique_count), f"{sent_total}触点 | {_pct(sent_unique_count, total)}", "#F5A623", 144, 0)
    kpis += _svg_kpi("已回复", str(reply_total), f"回复率 {_pct(reply_total, max(sent_unique_count,1))}", "#7ED321", 288, 0)

    plat_bars = [
        {"label": f"{v['label']}", "value": v["ok"], "color": v["color"],
         "pct": f"({v['ok']}/{v['has']})"}
        for v in plat_stats.values()
    ]
    bar_chart = _svg_bar(plat_bars, "触达明细", 420, 240)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f0f4f8;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:16px}}
.card{{background:#fff;border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
.card-title{{font-size:13px;font-weight:700;color:#334;margin-bottom:10px}}
h1{{font-size:18px;font-weight:800;color:#1a1a2e;margin-bottom:4px}}
.meta{{font-size:10px;color:#889;margin-bottom:12px}}
.flex{{display:flex;gap:12px;flex-wrap:wrap}}
.footer{{font-size:9px;color:#aab;text-align:center;margin-top:8px}}
</style></head><body style="width:460px">

<h1>DZATVAPE 总看板</h1>
<div class="meta">{now.strftime('%Y-%m-%d %H:%M')} (VPS)</div>

<div class="card">
    <svg width="440" height="72" xmlns="http://www.w3.org/2000/svg">{kpis}</svg>
</div>

<div class="card">
    <div class="card-title">全平台触达</div>
    {bar_chart}
</div>

<div class="card">
    <div class="card-title">WA AI 机器人</div>
    <div class="flex" style="justify-content:space-around;text-align:center;padding:8px 0">
        <div><div style="font-size:22px;font-weight:800;color:#25D366">{wa_chats}</div><div style="font-size:10px;color:#889">已聊客户</div></div>
        <div><div style="font-size:22px;font-weight:800;color:#4F8EF7">{wa_msgs}</div><div style="font-size:10px;color:#889">消息总数</div></div>
        <div><div style="font-size:22px;font-weight:800;color:#F5A623">{wa_hot}</div><div style="font-size:10px;color:#889">高意向</div></div>
        <div><div style="font-size:22px;font-weight:800;color:#7ED321">{wa_done}</div><div style="font-size:10px;color:#889">已完结</div></div>
    </div>
</div>

<div class="card">
    <div class="card-title">24H 快报</div>
    <div class="flex" style="justify-content:space-around;text-align:center">
        <div><div style="font-size:20px;font-weight:800;color:#4F8EF7">{h24_new}</div><div style="font-size:9px;color:#889">新线索</div></div>
        <div><div style="font-size:20px;font-weight:800;color:#25D366">{h24_sent}</div><div style="font-size:9px;color:#889">触达</div></div>
        <div><div style="font-size:20px;font-weight:800;color:#7C3AED">{h24_reply}</div><div style="font-size:9px;color:#889">回复</div></div>
    </div>
</div>

<div class="footer">DZATVAPE B2B · VPS 自动看板 · {now.strftime('%m/%d %H:%M')}</div>
</body></html>"""


def push_dashboard() -> bool:
    """生成 HTML 看板 → Playwright 截图 → 企微推送"""
    try:
        leads = _fetch_leads()
        if not leads:
            print("[Dashboard] No leads from CRM")
            return False

        html = build_html(leads)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 500, "height": 1200})
            page.set_content(html, wait_until="networkidle")
            page.wait_for_timeout(500)
            body_height = page.evaluate("document.body.scrollHeight")
            page.set_viewport_size({"width": 500, "height": body_height + 20})
            png = page.screenshot(full_page=True, type="png")
            browser.close()

        b64 = base64.b64encode(png).decode()
        md5 = hashlib.md5(png).hexdigest()
        resp = requests.post(
            WECHAT_WEBHOOK_URL,
            json={"msgtype": "image", "image": {"base64": b64, "md5": md5}},
            timeout=30,
        )
        ok = resp.status_code == 200 and resp.json().get("errcode") == 0
        print(f"[Dashboard] push: {'OK' if ok else f'FAIL {resp.text[:100]}'}")
        return ok
    except Exception as e:
        print(f"[Dashboard] error: {e}")
        import traceback
        traceback.print_exc()
        return False
