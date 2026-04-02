"""APScheduler-based daily scheduler.

Run with:
    uv run python -m arxiv_graph.scheduler.runner
"""

import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from arxiv_graph.scheduler.job import run_daily_job

_RUN_HOUR = 6   # 06:00 UTC daily
_RUN_MINUTE = 0


def _handle_shutdown(sig, frame):
    logger.info("Shutdown signal received — stopping scheduler")
    sys.exit(0)


def start() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily_job,
        trigger="cron",
        hour=_RUN_HOUR,
        minute=_RUN_MINUTE,
        id="daily_arxiv_crawl",
        name="Daily ArXiv Graph Crawl",
        misfire_grace_time=3600,  # allow up to 1h late start
    )

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info(f"Scheduler started — job runs daily at {_RUN_HOUR:02d}:{_RUN_MINUTE:02d} UTC")
    scheduler.start()


if __name__ == "__main__":
    start()
