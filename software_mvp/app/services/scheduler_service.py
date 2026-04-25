from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings
from ..database import SessionLocal
from ..models import Pipeline, Schedule
from .pipeline_service import run_pipeline

_scheduler: BackgroundScheduler | None = None


def validate_cron_expression(cron_expression: str, timezone: str) -> None:
    CronTrigger.from_crontab(cron_expression, timezone=timezone)


def _run_scheduled_pipeline(schedule_id: int) -> None:
    db = SessionLocal()
    try:
        schedule = db.get(Schedule, schedule_id)
        if not schedule or not schedule.is_active:
            return

        pipeline = db.get(Pipeline, schedule.pipeline_id)
        if not pipeline or not pipeline.is_active:
            return

        run_pipeline(db, pipeline)
    finally:
        db.close()


def _build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone=settings.app_timezone)


def init_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = _build_scheduler()
        _scheduler.start()
    reload_jobs()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def reload_jobs() -> None:
    if _scheduler is None:
        return

    _scheduler.remove_all_jobs()

    db = SessionLocal()
    try:
        schedules = db.query(Schedule).filter(Schedule.is_active.is_(True)).all()
        for schedule in schedules:
            try:
                trigger = CronTrigger.from_crontab(
                    schedule.cron_expression,
                    timezone=schedule.timezone,
                )
            except ValueError:
                continue

            _scheduler.add_job(
                _run_scheduled_pipeline,
                trigger=trigger,
                id=f"schedule-{schedule.id}",
                replace_existing=True,
                args=[schedule.id],
            )
    finally:
        db.close()


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler
