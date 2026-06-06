"""
LangGraph State 定义 — 获客引擎的共享状态。

计划 §4.2.4：StateGraph 贯穿所有节点。
"""

from typing import Annotated, Any, Optional, TypedDict
from operator import add


from operator import add


def _last(a, b):
    """Reducer: take the last written value."""
    return b


class DiscoveryState(TypedDict, total=False):
    """获客引擎全局状态。"""

    # Strategy 决策（单值，用 last-value reducer 防并行写冲突）
    market: Annotated[dict, _last]
    strategy_key: Annotated[str, _last]
    keywords: Annotated[list[str], _last]
    product_line: Annotated[str, _last]
    strategy_reasoning: Annotated[str, _last]

    # 搜索产出（多 Agent 并行写入，用 add reducer 合并列表）
    google_results: Annotated[list[dict], add]
    linkedin_results: Annotated[list[dict], add]
    social_results: Annotated[list[dict], add]
    cross_engine_results: Annotated[list[dict], add]

    # 验证/评分
    validated_leads: Annotated[list[dict], _last]
    scored_leads: Annotated[list[dict], _last]
    new_lead_ids: Annotated[list[str], _last]

    # 评估
    round_new_leads: Annotated[int, _last]
    should_continue: Annotated[bool, _last]

    # 护栏
    dry_rounds: Annotated[int, _last]
    token_budget_used: Annotated[int, _last]
    goal: Annotated[str, _last]

    # 历史
    history: Annotated[list[dict], _last]
    round_count: Annotated[int, _last]
