"""LOGI SEO Booster — FastAPI entrypoint.

The backend is organised in domain modules, each registering routes on the
shared `api` router defined in app_core:
- app_core          : env, db, encryption, models, auth
- routes_sites      : sites CRUD + Wix helpers
- routes_audit      : SEO audit + duplicate detection
- routes_billing    : workspaces, plans, Stripe
- routes_content    : AI generation, Pexels covers, drafts CRUD
- routes_publish    : Wix/FTP/GitHub publishing + HTML exports
- routes_google     : Google OAuth, GSC, Analytics, rank snapshots
- routes_linkedin   : LinkedIn OAuth + posting
- routes_pipeline   : publish pipeline + editorial calendar
- routes_social     : Meta (Facebook/Instagram) + Google Business Profile
- routes_dashboard  : performance, dashboard stats, 4-agents overview
- routes_workflows  : workflow builder + notifications
- routes_keywords   : keyword research
- routes_optimizer  : page optimizer
- routes_analysis   : AI visibility, keyword intelligence, business analyzer, competitors
"""
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.middleware.cors import CORSMiddleware

from app_core import app, api, db, client, logger

# Route modules — imported in dependency order; each registers on `api`
import routes_sites  # noqa: F401
import routes_audit  # noqa: F401
import routes_billing  # noqa: F401
import routes_content  # noqa: F401
import routes_publish  # noqa: F401
import routes_google  # noqa: F401
import routes_linkedin  # noqa: F401
import routes_pipeline  # noqa: F401
import routes_social  # noqa: F401
import routes_dashboard  # noqa: F401
import routes_workflows  # noqa: F401
import routes_keywords  # noqa: F401
import routes_optimizer  # noqa: F401
import routes_analysis  # noqa: F401
import routes_team  # noqa: F401
import routes_admin  # noqa: F401

from routes_google import _capture_rank_snapshot
from routes_pipeline import _calendar_processor_job
from routes_workflows import _workflow_processor_job


@api.get("/")
async def root():
    return {"app": "LOGI SEO Booster", "status": "ok"}


scheduler = AsyncIOScheduler(timezone="UTC")


async def _daily_rank_snapshots_job():
    """Background task: snapshot rank tracking for every site that has GSC + connected user."""
    try:
        sites = await db.sites.find({"gsc_site_url": {"$exists": True, "$ne": None}}, {"_id": 0}).to_list(1000)
        for s in sites:
            uid = s.get("user_id")
            sid = s.get("id")
            if not uid or not sid:
                continue
            try:
                user_doc = await db.users.find_one({"id": uid}, {"google_oauth": 1})
                if not (user_doc or {}).get("google_oauth", {}).get("refresh_token"):
                    continue
                res = await _capture_rank_snapshot(uid, sid, lookback_days=7)
                logger.info("Daily rank snapshot done for site %s: %s keywords", sid, res.get("count"))
            except Exception as exc:
                logger.warning("Rank snapshot failed for site %s: %s", sid, exc)
    except Exception as exc:
        logger.error("Scheduler job _daily_rank_snapshots_job error: %s", exc)


@app.on_event("startup")
async def _start_scheduler():
    try:
        scheduler.add_job(_daily_rank_snapshots_job, "cron", hour=4, minute=0, id="daily_rank_snapshots", replace_existing=True)
        scheduler.add_job(_calendar_processor_job, "interval", minutes=15, id="calendar_processor", replace_existing=True)
        scheduler.add_job(_workflow_processor_job, "interval", hours=1, id="workflow_processor", replace_existing=True)
        scheduler.start()
        logger.info("Scheduler started — daily rank snapshots at 04:00 UTC + calendar processor every 15 min + workflows hourly")
    except Exception as exc:
        logger.warning("Scheduler failed to start: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
