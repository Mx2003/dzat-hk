"""
高精度联系方式提取 — 移植旧系统 4 层架构。

L1: tel: href > wa.me > email > 社交链接 > 结构化电话
L2: Footer/Contact 隔离提取
L3: 12+ 国家号码格式
"""

import re
from urllib.parse import urlparse


# ── 号码验证 ────────────────────────────────────

def clean_number(raw: str) -> str:
    return re.sub(r'[^0-9]', '', raw)[:15]


def is_valid_phone(digits: str) -> bool:
    if not digits or len(digits) < 7 or len(digits) > 15:
        return False
    if len(set(digits)) == 1:
        return False
    if digits.startswith('000') and len(digits) < 10:
        return False
    # 过滤日期格式 YYYYMMDD
    if len(digits) == 8 and digits[:4].isdigit():
        y, m, d = digits[:4], digits[4:6], digits[6:8]
        if y in ('2023','2024','2025','2026') and '01' <= m <= '12' and '01' <= d <= '31':
            return False
    return True


# ── 12 国号码格式 ─────────────────────────────

_RE_PHONE_US = r'(?:\+?1[-.\s]?)?\(?[2-9][0-9]{2}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
_RE_PHONE_DE = r'\+?49\s*(?:\(?0\)?\s*)?[1-9][0-9]{0,4}\s*[0-9]{3,8}'
_RE_PHONE_FR = r'\+?33\s*[1-9](?:[\.\-\s]\d{2}){4}'
_RE_PHONE_UK = r'\+?44\s*[1-9]\d{1,3}\s*\d{3,4}\s*\d{3,4}'
_RE_PHONE_JP = r'\+?81\s*\d{1,4}[-\s]\d{1,4}[-\s]\d{4}'
_RE_PHONE_KR = r'\+?82\s*\d{1,2}[-\s]\d{3,4}[-\s]\d{4}'
_RE_PHONE_IT = r'\+?39\s*\d{2,4}\s*\d{6,8}'
_RE_PHONE_ES = r'\+?34\s*\d{2,3}\s*\d{3}\s*\d{2}\s*\d{2}'
_RE_PHONE_NL = r'\+?31\s*\d{1,3}\s*\d{3}\s*\d{4}'
_RE_PHONE_BR = r'\+?55\s*\(?\d{2}\)?\s*\d{4,5}[-\s]\d{4}'
_RE_PHONE_AE = r'\+?971\s*\d{1,2}\s*\d{3}\s*\d{4}'
_RE_PHONE_AU = r'\+?61\s*\d{1,2}\s*\d{4}\s*\d{4}'
_RE_PHONE_INTL = r'\+\d{1,3}[\d\s\-\(\)\.]{4,13}\d'

_ALL_PHONE = re.compile('|'.join(f'({p})' for p in [
    _RE_PHONE_US,_RE_PHONE_DE,_RE_PHONE_FR,_RE_PHONE_UK,
    _RE_PHONE_JP,_RE_PHONE_KR,_RE_PHONE_IT,_RE_PHONE_ES,
    _RE_PHONE_NL,_RE_PHONE_BR,_RE_PHONE_AE,_RE_PHONE_AU,_RE_PHONE_INTL,
]), re.I)


# ── Footer/Contact 隔离 ─────────────────────────

def _extract_footer_text(html: str) -> str:
    """隔离 footer/contact 区域，提取被主流程遗漏的联系方式。"""
    parts = []
    for tag in ['footer','.footer','#footer','[class*="footer"]','[id*="contact"]',
                'section.contact','div.contact-info','.contact-us']:
        m = re.search(f'<{tag}[^>]*>(.*?)</{tag.split("[")[0].replace(".","")}>', html, re.I|re.DOTALL)
        if m:
            parts.append(m.group(1))
    # 也找包含 contact/address 的 div
    for m in re.finditer(r'<(div|section)[^>]*(?:contact|address|footer)[^>]*>(.*?)</\1>', html, re.I|re.DOTALL):
        parts.append(m.group(2))
    return ' '.join(parts) if parts else ''


def _html_to_text(html: str) -> str:
    text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
    return re.sub(r'<[^>]+>', ' ', text)


# ── 占位符邮箱过滤 ──────────────────────────

_PLACEHOLDER_EMAILS = {'your@email.com','test@test.com','example@example.com','email@example.com',
                       'user@example.com','info@example.com','admin@example.com','hello@example.com',
                       'mail@example.com','contact@example.com','support@example.com','sales@example.com',
                       'you@example.com','me@example.com','name@email.com','email@email.com'}

_PLACEHOLDER_PHONE_PREFIXES = {'123-456','123456','555-000','555000','000-000','000000'}


# ── 主提取函数 ────────────────────────────────

# WhatsApp 信号词
_WA_CONTEXT = ['whatsapp','whats.app','wa.me','fa-whatsapp','icon-whatsapp','chat on whatsapp',
               'whatsapp-icon','whatsapp icon','WhatsApp','WA:']


def _score_wa_context(text_before_number: str) -> int:
    """评分：数字前面是不是 WhatsApp 标签。"""
    score = 0
    lowered = text_before_number.lower()
    for kw in _WA_CONTEXT:
        if kw.lower() in lowered:
            score += 30
            break
    return score


def extract_all_contacts(html: str) -> dict[str, str]:
    """L1+L2+L3 全量 + WhatsApp 6 种检测。"""
    result: dict[str, str] = {}

    # ── L1: tel: href ──────────────────────────
    tel = re.search(r'tel:(\+?[\d\-.\s]{6,15})', html, re.I)
    if tel:
        result["phone"] = tel.group(1).strip()

    # ── WhatsApp #1: wa.me href ─────────────────
    wa_me = re.search(r'(?:wa\.me/)(\+?[\d]{5,20})', html, re.I)
    if wa_me:
        result["whatsapp"] = wa_me.group(1).strip()

    # ── WhatsApp #2: api.whatsapp.com/send ──────
    if not result.get("whatsapp"):
        wa_api = re.search(r'(?:api\.whatsapp\.com|whatsapp\.com)/send\?phone=([+\d]{5,20})', html, re.I)
        if wa_api:
            digits = clean_number(wa_api.group(1))
            if is_valid_phone(digits):
                result["whatsapp"] = digits

    # ── Email ──────────────────────────────────
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    for e in emails:
        el = e.lower()
        if el in _PLACEHOLDER_EMAILS:
            continue
        if el.split('@')[-1] in {'example.com','domain.com','test.com'}:
            continue
        if any(kw in el for kw in ('noreply','no-reply','donotreply')):
            continue
        result["email"] = e
        break

    # ── L1: phone patterns ─────────────────────
    if not result.get("phone") or not result.get("whatsapp"):
        all_text = _html_to_text(html)
        phones = _ALL_PHONE.findall(all_text)
        best_wa = ""
        best_wa_score = 0

        for groups in phones:
            p = ''.join(g for g in groups if g).strip()
            digits = clean_number(p)
            if not is_valid_phone(digits):
                continue
            if any(digits.startswith(px.replace('-','').replace(' ','')) for px in _PLACEHOLDER_PHONE_PREFIXES):
                continue

            if not result.get("phone"):
                result["phone"] = p

            # WhatsApp 检测：看数字前 12 个字符是否有 WhatsApp 信号
            idx = all_text.find(p)
            if idx >= 0:
                pre = all_text[max(0, idx-12):idx].lower()
                wa_score = _score_wa_context(pre)
                if wa_score > 0 and wa_score > best_wa_score:
                    best_wa = digits
                    best_wa_score = wa_score

        if best_wa and not result.get("whatsapp"):
            result["whatsapp"] = best_wa

    # ── WhatsApp #3: 文本标签查找 ──────────────
    if not result.get("whatsapp"):
        text = _html_to_text(html)
        for pat in [r'(?:whatsapp|whats\s*app|wa)\s*[:#]?\s*(\+?[\d][\d\s\-\(\)\.]{6,18}[\d])',
                     r'(\+?[\d][\d\s\-\(\)\.]{6,18}[\d])\s*(?:whatsapp|whats\s*app)']:
            m = re.search(pat, text, re.I)
            if m:
                d = clean_number(m.group(1))
                if is_valid_phone(d):
                    result["whatsapp"] = d
                    break

    # ── L2: Footer/Contact 补充 ────────────────
    footer = _extract_footer_text(html)
    if footer:
        ft = _html_to_text(footer)
        if not result.get("email"):
            fe = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', ft)
            if fe: result["email"] = fe[0]
        if not result.get("phone"):
            fp = _ALL_PHONE.findall(ft)
            for groups in fp:
                p = ''.join(g for g in groups if g).strip()
                if is_valid_phone(clean_number(p)):
                    result["phone"] = p
                    break
        if not result.get("whatsapp"):
            for pat in [r'(?:whatsapp|wa)\s*[:#]?\s*(\+?[\d][\d\s\-\(\)\.]{6,18}[\d])']:
                m = re.search(pat, ft, re.I)
                if m:
                    d = clean_number(m.group(1))
                    if is_valid_phone(d):
                        result["whatsapp"] = d
                        break

    # ── Social ─────────────────────────────────
    social_map = {"instagram": r'instagram\.com/([a-zA-Z0-9._]+)',
                  "facebook": r'facebook\.com/([a-zA-Z0-9.]+)',
                  "linkedin": r'linkedin\.com/company/([a-zA-Z0-9\-]+)',
                  "x": r'(?:twitter|x)\.com/([a-zA-Z0-9_]+)'}
    for sn, sp in social_map.items():
        m = re.search(sp, html, re.I)
        if m:
            result[sn] = f"https://{sn if sn != 'x' else 'x'}.com/{m.group(1)}"

    return result
