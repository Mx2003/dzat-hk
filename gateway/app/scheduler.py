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
    """定时看板推送——从 EspoCRM 取全量数据，Python 过滤。"""
    try:
        import requests
        api = "http://espocrm/api/v1"
        h = {"X-Api-Key": "3f0f4ef281df645acdc6e30bf3d406ac"}

        r = requests.get(f"{api}/Lead?maxSize=100&sortBy=createdAt&desc=true", headers=h, timeout=15)
        if r.status_code != 200:
            logger.error(f"Dashboard API error: {r.status_code}")
            return
        data = r.json()
        leads = data.get("list", [])
        total = data.get("total", 0)

        # Python 侧过滤
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for l in leads if (l.get("createdAt") or "").startswith(today))

        score_dist = {"S": 0, "A": 0, "B": 0, "C": 0}
        countries = {}
        for l in leads:
            g = l.get("cScoreGrade") or "C"
            score_dist[g] = score_dist.get(g, 0) + 1
            c = l.get("addressCountry") or "?"
            countries[c] = countries.get(c, 0) + 1

        top5 = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]
        country_lines = "\n".join(f"> {c}: {n}" for c, n in top5)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        md = f"""##  DZAT B2B 日报
> {now}

**线索**: {total} | 今日 +{today_count}
**评分**: S:{score_dist['S']} A:{score_dist['A']} B:{score_dist['B']} C:{score_dist['C']}

**Top 市场**:
{country_lines}

---
>  DZAT Gateway 自动推送"""

        requests.post(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c5761dbf-e7e9-40a2-a678-467ed51379de",
            json={"msgtype": "markdown", "markdown": {"content": md}},
            timeout=10,
        )
        logger.info("[Scheduler] Dashboard pushed")
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
