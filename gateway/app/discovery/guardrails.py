"""
计划 §4.2.5 护栏 — 防止 AI 乱窜 + 防止幻觉污染数据。

GoalAnchor: 每 N 轮重注入原始目标，防止 Agent 跑偏
ConvergenceDetector: 连续零产出检测，自动停止
TokenBudget: Token 预算封顶
"""

import logging

logger = logging.getLogger("discovery.guardrails")


class GoalAnchor:
    """每 re_inject_every 轮重注入原始目标。"""

    def __init__(self, original_goal: str, re_inject_every: int = 5):
        self.original_goal = original_goal
        self.re_inject_every = re_inject_every

    def should_reinject(self, round_num: int) -> bool:
        return round_num > 0 and round_num % self.re_inject_every == 0


class ConvergenceDetector:
    """连续 dry_rounds_threshold 轮零产出 → 自动停止。"""

    def __init__(self, dry_rounds_threshold: int = 3):
        self.threshold = dry_rounds_threshold

    def should_stop(self, dry_rounds: int) -> bool:
        if dry_rounds >= self.threshold:
            logger.info(f"[Guard] Convergence: {dry_rounds} dry rounds, stopping")
            return True
        return False


class TokenBudget:
    """Token 预算管理。"""

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens

    def is_exhausted(self, used: int) -> bool:
        return used >= self.max_tokens
