"""
获客引擎编排 — LangGraph StateGraph。

计划 §4.2.4 执行图：Strategy → [4 Agents 并行] → 验证 → 入库 → 评估 → 循环。

并行采用 threading 在单节点内实现，避免 LangGraph fan-out 复杂度。
"""

import logging
import threading
from langgraph.graph import StateGraph, END

from .state import DiscoveryState
from .strategy import StrategyAgent
from .search_agents import google_search, linkedin_search, social_search, cross_engine_search
from .validation import level1_digital_footprint, level2_ai_judge, level3_gold_signals, detect_portrait
from .scoring import score_text, grade_score, detect_product_line, detect_customer_type
from .enrichment import enrich_lead
from .guardrails import GoalAnchor, ConvergenceDetector, TokenBudget

logger = logging.getLogger("discovery.graph")

# 翻译缓存
_trans_cache: dict[str, str] = {}

def _translate_cn(text: str) -> str:
    if not text or text in _trans_cache:
        return _trans_cache.get(text, text)
    try:
        from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
        import requests
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model":"deepseek-v4-flash","temperature":0.1,
                  "messages":[{"role":"user","content":f"将以下英文翻译为简体中文，只返回结果：\n{text[:300]}"}]},
            timeout=10,
        )
        if resp.status_code == 200:
            t = resp.json()["choices"][0]["message"]["content"].strip()
            _trans_cache[text] = t
            return t
    except Exception:
        pass
    return text

# 护栏
_goal_anchor = GoalAnchor("寻找海外电子烟中型分销商/品牌商", re_inject_every=5)
_convergence = ConvergenceDetector(dry_rounds_threshold=3)
_token_budget = TokenBudget(max_tokens=200000)


# ── Node: Strategy Agent ───────────────────────

def node_strategy(state: DiscoveryState) -> DiscoveryState:
    agent = StrategyAgent()
    history = state.get("history", [])
    recent = sum(h.get("leads", 0) for h in history[-3:]) if history else 0

    decision = agent.decide(history, recent)
    round_num = state.get("round_count", 0) + 1
    state["round_count"] = round_num

    if decision.get("strategy_key") == "STOP" or _convergence.should_stop(state.get("dry_rounds", 0)):
        state["should_continue"] = False
        return state

    market = decision.get("market", {})
    state["market"] = market
    state["strategy_key"] = decision.get("strategy_key", "")
    state["keywords"] = decision.get("keywords", ["vape distributor"])
    state["product_line"] = decision.get("product_line", "nicotine_vape")
    state["should_continue"] = True

    logger.info(f"[Graph] Strategy: {state['strategy_key']} @ {market.get('country','?')}")
    return state


# ── Node: 4 Agents 并行搜索 (threading) ────────

def _threaded(func, kw, country, results, name):
    try:
        r = func(kw, country)
        results[name] = r
        logger.info(f"[Graph] {name}: {len(r)} results")
    except Exception as e:
        logger.error(f"[Graph] {name} error: {e}")
        results[name] = []


def node_search(state: DiscoveryState) -> DiscoveryState:
    kws = state["keywords"] if state["keywords"] else ["vape distributor"]
    country = state["market"].get("country", "")

    results = {}
    results["google"] = google_search(kws, country)
    results["linkedin"] = []
    results["social"] = []
    results["cross_engine"] = cross_engine_search(kws, country)

    state["google_results"] = results.get("google", [])
    state["linkedin_results"] = results.get("linkedin", [])
    state["social_results"] = results.get("social", [])
    state["cross_engine_results"] = results.get("cross_engine", [])

    total = sum(len(v) for v in results.values())
    logger.info(f"[Graph] Search: {total} total from {len(results)} agents")
    return state


# ── Node: Merge + Validate ─────────────────────

def node_merge_validate(state: DiscoveryState) -> DiscoveryState:
    all_results = []
    for key in ["google_results", "linkedin_results", "social_results", "cross_engine_results"]:
        all_results.extend(state.get(key, []))

    VAPE_KW = {'vape','vaping','e-cigarette','e-cig','e-liquid','e-juice','nicotine','cannabis',
               'cbd','thc','delta','dab','vaporizer','pod','disposable','coil','atomizer',
               'cartridge','smoke','tobacco','hemp','cigarette','puff','cigarrillo',
               'electronico','vaporizador','svapo','dampfen','ezigarette','베이프','電子タバコ'}
    validated = []
    for row in all_results:
        text = f"{row.get('公司名','')} {row.get('经营介绍','')}".lower()
        if not any(kw in text for kw in VAPE_KW):
            continue
        l1_ok, l1_score, l1_reason = level1_digital_footprint(row)
        row["命中信号"] = f"L1:{l1_reason}"
        row["L1_score"] = l1_score
        if l1_ok or int(row.get("评分", 0)) >= 30:
            is_biz, conf, biz_type, evidence = level2_ai_judge(row)
            row["置信度"] = conf
            row["命中信号"] += f";L2:{biz_type}"
            if not is_biz and conf >= 50:
                continue
            gold = level3_gold_signals(row)
            if gold:
                row["金矿信号"] = ";".join(gold)
        validated.append(row)

    state["validated_leads"] = validated
    logger.info(f"[Graph] Validate: {len(validated)}/{len(all_results)} passed")
    return state


# ── Node: Enrich ────────────────────────────────

def node_enrich(state: DiscoveryState) -> DiscoveryState:
    enriched = []
    for r in state["validated_leads"]:
        r = enrich_lead(r)
        # 翻译英文描述为中文
        desc = r.get("经营介绍", "")
        if desc and not any('一' <= c <= '鿿' for c in desc):
            r["经营介绍"] = _translate_cn(desc)
        enriched.append(r)
    state["validated_leads"] = enriched
    return state


# ── Node: Score ─────────────────────────────────

def node_score(state: DiscoveryState) -> DiscoveryState:
    scored = []
    for row in state["validated_leads"]:
        text = f"{row.get('公司名','')} {row.get('经营介绍','')} {row.get('来源关键词','')}"
        s, hits, penalties = score_text(text)
        if row.get("官网", "").startswith("http"):
            s += 10
        # 客户画像检测 + 加分
        portrait = detect_portrait(row)
        s += portrait.get("bonus_score", 0)
        row["评分"] = max(5, min(100, s + row.get("L1_score", 0)))
        row["评分等级"] = grade_score(row["评分"])
        row["命中关键词"] = ";".join(hits)
        row["客户类型"] = detect_customer_type(text)
        row["客户画像"] = portrait.get("primary_portrait", "none")
        pl, _ = detect_product_line(text)
        row["产品线"] = pl if pl != "unknown" else row.get("产品线", "nicotine_vape")
        scored.append(row)
    state["scored_leads"] = sorted(scored, key=lambda x: x.get("评分", 0), reverse=True)
    logger.info(f"[Graph] Score: {len(scored)} leads")
    return state


# ── Node: Upsert ────────────────────────────────

def node_upsert(state: DiscoveryState) -> DiscoveryState:
    from .pipeline import DiscoveryPipeline
    p = DiscoveryPipeline()
    ids = []
    # 垃圾公司名过滤
    JUNK = {"cloudflare", "outlook", "challenges", "login", "signin", "signup", "webmail",
            "mail.", "consent.", "cookie.", "oath.", "live.com", "microsoftonline",
            "google", "facebook", "instagram", "linkedin", "twitter", "youtube",
            "bing", "yahoo", "microsoft", "apple", "amazon", "wikipedia",
            "cookie", "privacy", "terms", "404", "error", "page not found"}
    for row in state["scored_leads"]:
        name = (row.get("公司名") or "").lower()
        if any(j in name for j in JUNK) or len(name) < 3:
            logger.info(f"[Graph] Upsert SKIP (junk): {row.get('公司名','?')[:30]}")
            continue
        try:
            lid = p._upsert_lead(row)
            if lid:
                ids.append(lid)
                logger.info(f"[Graph] Upsert OK: {row.get('公司名','?')[:25]}")
            else:
                logger.warning(f"[Graph] Upsert FAIL: {row.get('公司名','?')[:25]}")
        except Exception as e:
            logger.error(f"[Graph] Upsert ERROR: {row.get('公司名','?')[:25]}: {e}")
    state["new_lead_ids"] = ids
    logger.info(f"[Graph] Upsert: {len(ids)} leads (new + existing)")
    return state


# ── Node: Evaluate ──────────────────────────────

def node_evaluate(state: DiscoveryState) -> DiscoveryState:
    new = len(state.get("new_lead_ids", []))
    state["round_new_leads"] = new

    history = state.get("history", [])
    history.append({"market": state["market"].get("country", ""),
                    "city": state["market"].get("city", ""),
                    "strategy": state.get("strategy_key", ""), "leads": new})
    state["history"] = history

    dry = state.get("dry_rounds", 0)
    dry = 0 if new > 0 else dry + 1
    state["dry_rounds"] = dry

    if _convergence.should_stop(dry):
        state["should_continue"] = False
    elif state.get("round_count", 0) >= 3:
        state["should_continue"] = False

    logger.info(f"[Graph] Evaluate: {new} new, dry={dry}, continue={state.get('should_continue',True)}")
    return state


# ── Build Graph ────────────────────────────────

def build_graph():
    w = StateGraph(DiscoveryState)
    w.add_node("strategy", node_strategy)
    w.add_node("search", node_search)
    w.add_node("merge_validate", node_merge_validate)
    w.add_node("enrich", node_enrich)
    w.add_node("score", node_score)
    w.add_node("upsert", node_upsert)
    w.add_node("evaluate", node_evaluate)

    w.set_entry_point("strategy")
    w.add_edge("strategy", "search")
    w.add_edge("search", "merge_validate")
    w.add_edge("merge_validate", "enrich")
    w.add_edge("enrich", "score")
    w.add_edge("score", "upsert")
    w.add_edge("upsert", "evaluate")
    return w.compile()


_discovery_graph = None

def get_graph():
    global _discovery_graph
    if _discovery_graph is None:
        _discovery_graph = build_graph()
    return _discovery_graph


def run_discovery(initial_state: dict = None, max_rounds: int = 3) -> dict:
    """手动循环运行获客引擎。避免 LangGraph 回环路由问题。

    每轮：strategy → search → validate → enrich → score → upsert → evaluate
    """
    g = build_graph()
    state = initial_state or {
        "history": [], "round_count": 0, "dry_rounds": 0,
        "token_budget_used": 0, "goal": "find overseas vape distributors",
    }
    total_leads = 0

    for i in range(max_rounds):
        logger.info(f"[Discovery] === Round {i+1}/{max_rounds} ===")
        state = g.invoke(state)
        new = len(state.get("new_lead_ids", []))
        total_leads += new
        logger.info(f"[Discovery] Round {i+1}: {new} leads (total: {total_leads})")
        if not state.get("should_continue", True):
            logger.info(f"[Discovery] Stopped by should_continue=False")
            break

    state["total_leads"] = total_leads
    logger.info(f"[Discovery] FINISHED: {total_leads} total leads in {i+1} rounds")
    return state
