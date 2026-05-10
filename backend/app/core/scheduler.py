from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from datetime import datetime, timedelta, timezone
from app.services.update_service import run_bulk_update_task, run_realtime_cache_update, run_autonomous_cycle

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def start_scheduler():
    """Starts the task scheduler."""
    # Real-time Heatmap refresh (Every 15 minutes)
    scheduler.add_job(
        run_realtime_cache_update,
        'interval',
        minutes=15,
        id='realtime_market_sync'
    )

    # Autonomous System Cycle (Every 60 seconds)
    # NOTE: The cycle only does real work on 10/30-min cooldowns, so 5s was
    # pure overhead — it blocked the async event loop and caused API timeouts.
    scheduler.add_job(
        run_autonomous_cycle,
        'interval',
        seconds=60,
        id='autonomous_system_cycle'
    )

    # Schedule to run every day at 17:00 IST (Indian Standard Time)
    # Using cron trigger
    # Note: Container might be in UTC. 17:00 IST is 11:30 UTC.
    # It is safer to use the explicit timezone if available, or just assume UTC.
    # Let's assume container is UTC for now. 11:30 UTC = 17:00 IST.
    
    # Adding a job to the scheduler
    from app.core.config import settings
    
    # Schedule using configured UTC time
    scheduler.add_job(
        run_bulk_update_task, 
        'cron', 
        hour=settings.SCHEDULER_TIME_UTC_HOUR, 
        minute=settings.SCHEDULER_TIME_UTC_MINUTE
    )
    
    # Phase 6: Nightly outcome grading
    scheduler.add_job(
        _grade_outcomes_task,
        'cron',
        hour=settings.GRADE_OUTCOMES_HOUR,
        minute=settings.GRADE_OUTCOMES_MINUTE,
        id='grade_outcomes_nightly',
    )

    # Paper Trading: Open positions
    scheduler.add_job(
        _open_paper_positions,
        'cron',
        hour=settings.PAPER_OPEN_HOUR,
        minute=settings.PAPER_OPEN_MINUTE,
        id='paper_open_positions',
    )

    # Paper Trading: Monitor stops/targets
    scheduler.add_job(
        _monitor_paper_positions,
        'cron',
        hour=settings.PAPER_MONITOR_HOUR,
        minute=settings.PAPER_MONITOR_MINUTE,
        id='paper_monitor_positions',
    )

    # Watchdog: Check scheduler health
    scheduler.add_job(
        _watchdog_check,
        'interval',
        hours=settings.WATCHDOG_INTERVAL_HOURS,
        id='watchdog_health',
    )
    
    logger.info("Scheduler configured with 5 jobs: bulk_update, outcome_grading, paper_open, paper_monitor, watchdog")
    
    
    # Check for stale data and trigger update if needed
    _check_and_trigger_startup_update()
    
    scheduler.start()
    logger.info("Scheduler started.")

def shutdown_scheduler():
    """Shuts down the task scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down.")


def _grade_outcomes_task():
    """Nightly outcome grading — Phase 6 self-healing feedback loop."""
    db = None
    try:
        from app.db.session import SessionLocal
        from app.services.outcome_tracker import OutcomeTracker

        db = SessionLocal()
        tracker = OutcomeTracker()
        result = tracker.grade_pending_signals(db)
        logger.info(f"Outcome grading complete: {result}")
    except Exception as e:
        logger.error(f"Outcome grading failed: {e}")
    finally:
        if db:
            db.close()


def _open_paper_positions():
    """Opens paper trades for high-confidence BUY signals at 9:20 AM IST (3:50 UTC)."""
    db = None
    try:
        from app.db.session import SessionLocal
        from app.db.models import Signal
        from app.services.paper_trader import PaperTradingEngine
        from datetime import datetime, timedelta

        db = SessionLocal()
        engine = PaperTradingEngine()

        today_signals = db.query(Signal).filter(
            Signal.signal_type == 'BUY',
            Signal.confidence >= 0.75,
            Signal.created_at >= datetime.utcnow() - timedelta(hours=20),
        ).all()

        opened = 0
        for signal in today_signals:
            trade = engine.open_trade_from_signal(signal, db)
            if trade:
                opened += 1

        logger.info(f"Paper trading: opened {opened} from {len(today_signals)} signals")
    except Exception as e:
        logger.error(f"Paper trade open failed: {e}")
    finally:
        if db:
            db.close()


def _monitor_paper_positions():
    """Monitors paper positions for stop/target at 3:45 PM IST (10:15 UTC)."""
    db = None
    try:
        from app.db.session import SessionLocal
        from app.services.paper_trader import PaperTradingEngine

        db = SessionLocal()
        engine = PaperTradingEngine()
        result = engine.monitor_open_positions(db)
        logger.info(f"Paper monitor: {result}")
    except Exception as e:
        logger.error(f"Paper monitor failed: {e}")
    finally:
        if db:
            db.close()


async def _watchdog_check():
    """Every-2-hour scheduler health check with Telegram alert."""
    db = None
    try:
        from app.db.session import SessionLocal
        from app.services.watchdog import check_scheduler_health

        db = SessionLocal()
        await check_scheduler_health(db)
    except Exception as e:
        logger.error(f"Watchdog failed: {e}")
    finally:
        if db:
            db.close()


def _check_and_trigger_startup_update():
    """Checks if the data is stale on startup and triggers a background update."""
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.db.models import Signal
    
    db = None
    try:
        db = SessionLocal()
        last_signal = db.query(Signal).order_by(Signal.created_at.desc()).first()
        
        should_update = False
        if not last_signal:
            logger.info("Startup: No signals found in DB. Triggering initial update.")
            should_update = True
        else:
            # Check age
            age_hours = (datetime.now(timezone.utc) - last_signal.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if age_hours > settings.STARTUP_UPDATE_THRESHOLD_HOURS:
                logger.info(f"Startup: Latest signal is {round(age_hours, 1)} hours old (Threshold: {settings.STARTUP_UPDATE_THRESHOLD_HOURS}). Triggering update.")
                should_update = True
            else:
                logger.info(f"Startup: Data is fresh ({round(age_hours, 1)} hours old). No immediate update needed.")
        
        if should_update:
            # Run in a separate thread or just rely on the autonomous cycle that will trigger in 5 mins?
            # Actually, the 5-min cooldown is safer, but user wants it "now".
            # We can just call it once here.
            import threading
            threading.Thread(target=run_bulk_update_task, daemon=True).start()
            logger.info("Startup: Background update task dispatched.")
            
    except Exception as e:
        logger.error(f"Startup update check failed: {e}")
    finally:
        if db:
            db.close()
