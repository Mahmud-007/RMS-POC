"""APScheduler setup. Weekly base retrain + nightly metrics refresh."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_retrain_base, CronTrigger(day_of_week="mon", hour=3, minute=0), id="retrain_base")
    _scheduler.add_job(_refresh_metrics, CronTrigger(hour=2, minute=0), id="refresh_metrics")
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _retrain_base() -> None:
    from app.train.train_base import run as run_train
    run_train()


def _refresh_metrics() -> None:
    raise NotImplementedError
