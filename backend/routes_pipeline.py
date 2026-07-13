from datetime import datetime
from datetime import timedelta
from datetime import timezone
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field
from typing import List
from typing import Literal
from typing import Optional
import asyncio
from app_core import ContentGenerateRequest, api, db, gen_id, get_current_user, logger, now_iso
from routes_sites import _get_user_site
from routes_content import _do_generate_content
from routes_publish import publish_draft_to_github
from routes_linkedin import publish_draft_to_linkedin

async def _do_publish_pipeline(user_id: str, draft_id: str, auto_github: bool, auto_linkedin: bool):
    """Run the publish pipeline (GitHub then LinkedIn) for a draft. Errors are logged but don't stop the pipeline."""
    if auto_github:
        try:
            user = {"id": user_id}
            await publish_draft_to_github(draft_id, user=user)
        except Exception as exc:
            logger.warning("Auto GH publish failed for %s: %s", draft_id, exc)
    if auto_linkedin:
        try:
            user = {"id": user_id}
            await publish_draft_to_linkedin(draft_id, user=user)
        except Exception as exc:
            logger.warning("Auto LI publish failed for %s: %s", draft_id, exc)


class BatchGenerateItem(BaseModel):
    topic: str
    city: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    content_type: Literal["article", "page_locale", "faq"] = "article"
    target_length: Literal["court", "moyen", "long"] = "moyen"
    extra_instructions: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    site_id: str
    items: List[BatchGenerateItem]
    tone: Literal["professionnel", "amical", "expert"] = "professionnel"
    auto_publish_github: bool = False
    auto_publish_linkedin: bool = False


@api.post("/content/batch-generate")
async def batch_generate(req: BatchGenerateRequest, user=Depends(get_current_user)):
    """Generate multiple articles in background. Returns batch_id to poll."""
    if not req.items:
        raise HTTPException(400, "Liste d'items vide")
    if len(req.items) > 50:
        raise HTTPException(400, "Maximum 50 articles par lot")

    batch_id = gen_id()
    await db.batch_jobs.insert_one({
        "id": batch_id,
        "user_id": user["id"],
        "site_id": req.site_id,
        "total": len(req.items),
        "completed": 0,
        "failed": 0,
        "status": "running",
        "auto_publish_github": req.auto_publish_github,
        "auto_publish_linkedin": req.auto_publish_linkedin,
        "items": [{"index": i, "topic": it.topic, "city": it.city, "status": "pending", "draft_id": None, "error": None} for i, it in enumerate(req.items)],
        "created_at": now_iso(),
        "completed_at": None,
    })

    async def _run_batch():
        for i, item in enumerate(req.items):
            try:
                gen_req = ContentGenerateRequest(
                    site_id=req.site_id,
                    content_type=item.content_type,
                    topic=item.topic,
                    keywords=item.keywords,
                    city=item.city,
                    tone=req.tone,
                    target_length=item.target_length,
                    extra_instructions=item.extra_instructions,
                )
                draft = await _do_generate_content(gen_req, user["id"])
                await _do_publish_pipeline(user["id"], draft.id, req.auto_publish_github, req.auto_publish_linkedin)
                await db.batch_jobs.update_one(
                    {"id": batch_id},
                    {"$set": {f"items.{i}.status": "completed", f"items.{i}.draft_id": draft.id}, "$inc": {"completed": 1}},
                )
            except Exception as exc:
                logger.warning("Batch item %d failed: %s", i, exc)
                await db.batch_jobs.update_one(
                    {"id": batch_id},
                    {"$set": {f"items.{i}.status": "failed", f"items.{i}.error": str(exc)}, "$inc": {"failed": 1}},
                )
        await db.batch_jobs.update_one(
            {"id": batch_id},
            {"$set": {"status": "completed", "completed_at": now_iso()}},
        )

    asyncio.create_task(_run_batch())
    return {"batch_id": batch_id, "total": len(req.items)}


@api.get("/content/batch-jobs/{batch_id}")
async def get_batch_job(batch_id: str, user=Depends(get_current_user)):
    job = await db.batch_jobs.find_one({"id": batch_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0})
    if not job:
        raise HTTPException(404, "Batch introuvable")
    return job


@api.get("/content/batch-jobs")
async def list_batch_jobs(user=Depends(get_current_user)):
    items = await db.batch_jobs.find(
        {"user_id": user["id"]},
        {"_id": 0, "user_id": 0, "items": 0},
    ).sort("created_at", -1).to_list(20)
    return items


# ---------------------------------------------------------------------------
# Editorial Calendar (Niveau 3) — scheduled publication queue
# ---------------------------------------------------------------------------
class CalendarItemCreate(BaseModel):
    site_id: str
    topic: str
    city: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    content_type: Literal["article", "page_locale", "faq"] = "article"
    target_length: Literal["court", "moyen", "long"] = "moyen"
    tone: Literal["professionnel", "amical", "expert"] = "professionnel"
    extra_instructions: Optional[str] = None
    scheduled_at: str  # ISO datetime
    auto_publish_github: bool = True
    auto_publish_linkedin: bool = False


@api.post("/calendar")
async def create_calendar_item(payload: CalendarItemCreate, user=Depends(get_current_user)):
    await _get_user_site(payload.site_id, user)
    item = {
        "id": gen_id(),
        "user_id": user["id"],
        **payload.model_dump(),
        "status": "scheduled",
        "draft_id": None,
        "error": None,
        "created_at": now_iso(),
        "processed_at": None,
    }
    await db.calendar.insert_one(item)
    return {**item, "_id": None}


@api.get("/calendar")
async def list_calendar(site_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"user_id": user["id"]}
    if site_id:
        q["site_id"] = site_id
    items = await db.calendar.find(q, {"_id": 0, "user_id": 0}).sort("scheduled_at", 1).to_list(500)
    return items


@api.delete("/calendar/{item_id}")
async def delete_calendar_item(item_id: str, user=Depends(get_current_user)):
    res = await db.calendar.delete_one({"id": item_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Élément introuvable")
    return {"ok": True}


class BulkCalendarRequest(BaseModel):
    site_id: str
    items: List[BatchGenerateItem]
    interval_days: int = Field(2, ge=1, le=30)  # 1 article tous les N jours
    start_at: Optional[str] = None  # ISO datetime, default: tomorrow 10:00
    auto_publish_github: bool = True
    auto_publish_linkedin: bool = False
    tone: Literal["professionnel", "amical", "expert"] = "professionnel"


@api.post("/calendar/bulk")
async def bulk_schedule(req: BulkCalendarRequest, user=Depends(get_current_user)):
    """Schedule many articles at regular intervals. Returns the list of created calendar items."""
    await _get_user_site(req.site_id, user)
    if not req.items:
        raise HTTPException(400, "Liste vide")
    if len(req.items) > 100:
        raise HTTPException(400, "Maximum 100 articles par planification")
    if req.start_at:
        start = datetime.fromisoformat(req.start_at.replace("Z", "+00:00"))
    else:
        start = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    created = []
    for i, it in enumerate(req.items):
        scheduled = start + timedelta(days=i * req.interval_days)
        doc = {
            "id": gen_id(),
            "user_id": user["id"],
            "site_id": req.site_id,
            "topic": it.topic,
            "city": it.city,
            "keywords": it.keywords,
            "content_type": it.content_type,
            "target_length": it.target_length,
            "tone": req.tone,
            "extra_instructions": it.extra_instructions,
            "scheduled_at": scheduled.isoformat(),
            "auto_publish_github": req.auto_publish_github,
            "auto_publish_linkedin": req.auto_publish_linkedin,
            "status": "scheduled",
            "draft_id": None,
            "error": None,
            "created_at": now_iso(),
            "processed_at": None,
        }
        await db.calendar.insert_one(doc)
        created.append({k: v for k, v in doc.items() if k != "_id"})
    return {"created": len(created), "items": created}


async def _calendar_processor_job():
    """Scheduler job — every 15 min, picks up due calendar items and processes them."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = db.calendar.find({"status": "scheduled", "scheduled_at": {"$lte": now}}, {"_id": 0})
        due = await cursor.to_list(50)
        for item in due:
            try:
                # Mark as processing first to avoid double-processing
                res = await db.calendar.update_one(
                    {"id": item["id"], "status": "scheduled"},
                    {"$set": {"status": "processing"}},
                )
                if res.modified_count == 0:
                    continue
                req = ContentGenerateRequest(
                    site_id=item["site_id"],
                    content_type=item.get("content_type") or "article",
                    topic=item["topic"],
                    keywords=item.get("keywords", []),
                    city=item.get("city"),
                    tone=item.get("tone") or "professionnel",
                    target_length=item.get("target_length") or "moyen",
                    extra_instructions=item.get("extra_instructions"),
                )
                draft = await _do_generate_content(req, item["user_id"])
                await _do_publish_pipeline(
                    item["user_id"], draft.id,
                    item.get("auto_publish_github", True),
                    item.get("auto_publish_linkedin", False),
                )
                await db.calendar.update_one(
                    {"id": item["id"]},
                    {"$set": {"status": "completed", "draft_id": draft.id, "processed_at": now_iso()}},
                )
                logger.info("Calendar item %s completed → draft %s", item["id"], draft.id)
            except Exception as exc:
                logger.exception("Calendar item %s failed", item["id"])
                await db.calendar.update_one(
                    {"id": item["id"]},
                    {"$set": {"status": "failed", "error": str(exc), "processed_at": now_iso()}},
                )
    except Exception as exc:
        logger.error("Calendar processor error: %s", exc)


