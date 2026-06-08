"""
定时调度器 — APScheduler。

计划 §5.3：Gateway 就是唯一的调度中枢。
- 每天 08:00/14:00/20:00 跑获客
- 每天 10:00/16:00 跑触达
- 每天 18:00 推看板到企微
"""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler")

_scheduler = BackgroundScheduler()


def _run_discovery():
    """定时获客任务。"""
    try:
        from .discovery.graph import run_discovery
        logger.info("[Scheduler] Starting discovery...")
        r = run_discovery(max_rounds=3)
        logger.info(f"[Scheduler] Discovery done: {r.get('total_leads', 0)} leads")
    except Exception as e:
        logger.error(f"[Scheduler] Discovery error: {e}")


def _run_outreach():
    """定时触达任务。"""
    try:
        from .outreach.dispatcher import OutreachDispatcher
        d = OutreachDispatcher()
        results = d.run_all()
        total = sum(len(v) for v in results.values())
        logger.info(f"[Scheduler] Outreach done: {total} sent")
    except Exception as e:
        logger.error(f"[Scheduler] Outreach error: {e}")


def _push_dashboard():
    """定时看板推送——HTML 图表 + Playwright 截图 → 企微图片。"""
    try:
        from .dashboard_vps import push_dashboard
        ok = push_dashboard()
        logger.info(f"[Scheduler] Dashboard {'OK' if ok else 'FAIL'}")
    except Exception as e:
        logger.error(f"[Scheduler] Dashboard error: {e}")


def start_scheduler():
    # _scheduler.add_job(_run_discovery, CronTrigger(hour="8,14,20", minute="0"), id="discovery")  # 获客已关
    _scheduler.add_job(_run_outreach, CronTrigger(hour="10,16", minute="0", timezone="Asia/Hong_Kong"), id="outreach")
    _scheduler.add_job(_push_dashboard, CronTrigger(hour="18", minute="0", timezone="Asia/Hong_Kong"), id="dashboard")
    _scheduler.start()
    logger.info("[Scheduler] started: outreach@10/16, dashboard@18")


def stop_scheduler():
    _scheduler.shutdown(wait=False)
    logger.info("[Scheduler] stopped")


def get_scheduler() -> BackgroundScheduler:
    return _scheduler
