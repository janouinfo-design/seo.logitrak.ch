from datetime import datetime
from datetime import timedelta
from datetime import timezone
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
import asyncio
from app_core import ContentGenerateRequest, api, db, gen_id, get_current_user, logger, now_iso
from routes_sites import _get_user_site
from routes_audit import run_audit
from routes_content import _do_generate_content

# ---------------------------------------------------------------------------
# Workflow Builder (SI déclencheur ALORS actions) + Notifications
# ---------------------------------------------------------------------------
WORKFLOW_TRIGGERS = ("rank_drop", "ai_visibility_drop", "no_publication")
WORKFLOW_ACTIONS = ("notify", "generate_draft", "run_audit")


class WorkflowCreate(BaseModel):
    site_id: str
    name: str
    trigger_type: Literal["rank_drop", "ai_visibility_drop", "no_publication"]
    trigger_params: Dict[str, Any] = {}
    actions: List[Literal["notify", "generate_draft", "run_audit"]]
    enabled: bool = True


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    trigger_params: Optional[Dict[str, Any]] = None
    actions: Optional[List[Literal["notify", "generate_draft", "run_audit"]]] = None
    enabled: Optional[bool] = None


async def _notify(user_id: str, site_id: str, title: str, message: str, workflow: Optional[dict] = None):
    await db.notifications.insert_one({
        "id": gen_id(),
        "user_id": user_id,
        "site_id": site_id,
        "workflow_id": (workflow or {}).get("id"),
        "workflow_name": (workflow or {}).get("name"),
        "title": title,
        "message": message,
        "read": False,
        "created_at": now_iso(),
    })


async def _evaluate_workflow_trigger(wf: dict) -> tuple:
    """Returns (fired: bool, reason: str, context: dict)."""
    uid, sid = wf["user_id"], wf["site_id"]
    params = wf.get("trigger_params") or {}
    ttype = wf["trigger_type"]

    if ttype == "rank_drop":
        threshold = int(params.get("threshold", 5))
        dates = sorted(await db.rank_snapshots.distinct(
            "snapshot_date", {"user_id": uid, "site_id": sid}))
        if len(dates) < 2:
            return False, "Pas assez d'historique de positions (connectez Google Search Console et attendez 2 snapshots quotidiens).", {}
        prev_docs = await db.rank_snapshots.find(
            {"user_id": uid, "site_id": sid, "snapshot_date": dates[-2]}, {"_id": 0}).to_list(2000)
        curr_docs = await db.rank_snapshots.find(
            {"user_id": uid, "site_id": sid, "snapshot_date": dates[-1]}, {"_id": 0}).to_list(2000)
        prev = {s["keyword"]: s.get("position") for s in prev_docs}
        drops = []
        for s in curr_docs:
            p = prev.get(s["keyword"])
            if p and s.get("position") and s["position"] - p >= threshold:
                drops.append({"keyword": s["keyword"], "from": round(p, 1), "to": round(s["position"], 1)})
        if drops:
            drops.sort(key=lambda x: -(x["to"] - x["from"]))
            kws = ", ".join(f"« {d['keyword']} » ({d['from']}→{d['to']})" for d in drops[:3])
            return True, f"{len(drops)} mot(s)-clé(s) ont chuté de ≥{threshold} positions : {kws}", {"drops": drops[:5]}
        return False, f"Aucune chute de ≥{threshold} positions entre {dates[-2]} et {dates[-1]}.", {}

    if ttype == "ai_visibility_drop":
        threshold = int(params.get("threshold", 5))
        reps = await db.ai_visibility_reports.find(
            {"user_id": uid, "site_id": sid}, {"_id": 0, "global_score": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(2)
        if len(reps) < 2:
            return False, "Pas assez d'analyses AI Visibility (2 minimum pour comparer).", {}
        curr, prev = reps[0].get("global_score", 0), reps[1].get("global_score", 0)
        diff = prev - curr
        if diff >= threshold:
            return True, f"Score AI Visibility en baisse de {diff} points ({prev} → {curr}).", {"from": prev, "to": curr}
        return False, f"Score AI Visibility stable ({prev} → {curr}, seuil {threshold} pts).", {}

    # no_publication
    days = int(params.get("days", 7))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    recent = await db.drafts.find_one({
        "user_id": uid, "site_id": sid,
        "$or": [
            {"status": "published", "updated_at": {"$gte": cutoff}},
            {"github_committed_at": {"$gte": cutoff}},
        ],
    }, {"_id": 0, "id": 1})
    if recent:
        return False, f"Une publication a eu lieu dans les {days} derniers jours.", {}
    return True, f"Aucune publication depuis plus de {days} jours.", {"days": days}


async def _execute_workflow_actions(wf: dict, reason: str, context: dict, background: bool = False) -> list:
    uid, sid = wf["user_id"], wf["site_id"]
    results = []
    for action in wf.get("actions", []):
        try:
            if action == "notify":
                await _notify(uid, sid, f"Workflow « {wf['name']} » déclenché", reason, wf)
                results.append({"action": "notify", "ok": True, "detail": "Notification créée"})
            elif action == "generate_draft":
                drops = context.get("drops") or []
                if drops:
                    kw = drops[0]["keyword"]
                    topic = f"Article de renfort SEO sur « {kw} » (position Google en baisse)"
                    keywords = [d["keyword"] for d in drops[:3]]
                elif wf["trigger_type"] == "ai_visibility_drop":
                    topic = "Article d'autorité et d'expertise pour renforcer la visibilité de l'entreprise dans les réponses des IA (ChatGPT, Gemini, Claude)"
                    keywords = []
                else:
                    topic = "Nouvel article frais pour maintenir la régularité de publication et le référencement"
                    keywords = []
                req = ContentGenerateRequest(site_id=sid, content_type="article", topic=topic, keywords=keywords)
                if background:
                    # HTTP path: generation takes 60-120s (> ingress timeout) → fire-and-forget
                    asyncio.create_task(_bg_workflow_generate_draft(wf, req))
                    results.append({"action": "generate_draft", "ok": True,
                                    "detail": "Génération du brouillon lancée en arrière-plan (1-2 min) — surveillez vos notifications et la page Brouillons."})
                else:
                    draft = await _do_generate_content(req, uid)
                    await _notify(uid, sid, "Brouillon généré automatiquement",
                                  f"Le workflow « {wf['name']} » a rédigé : {draft.title}. Relisez-le dans Brouillons.", wf)
                    results.append({"action": "generate_draft", "ok": True, "detail": f"Brouillon créé : {draft.title}", "draft_id": draft.id})
            elif action == "run_audit":
                report = await run_audit(sid, user={"id": uid})
                await _notify(uid, sid, "Audit SEO relancé automatiquement",
                              f"Le workflow « {wf['name']} » a lancé un audit : score {report.score}/100, {len(report.issues)} problèmes détectés.", wf)
                results.append({"action": "run_audit", "ok": True, "detail": f"Audit terminé : score {report.score}/100"})
        except HTTPException as exc:
            results.append({"action": action, "ok": False, "detail": str(exc.detail)})
        except Exception as exc:
            logger.exception("Workflow %s action %s failed", wf["id"], action)
            results.append({"action": action, "ok": False, "detail": str(exc)[:200]})
    return results


async def _bg_workflow_generate_draft(wf: dict, req: "ContentGenerateRequest"):
    """Background generation for manual workflow runs (avoids ingress timeout)."""
    uid, sid = wf["user_id"], wf["site_id"]
    try:
        draft = await _do_generate_content(req, uid)
        detail = {"action": "generate_draft", "ok": True, "detail": f"Brouillon créé : {draft.title}", "draft_id": draft.id}
        await _notify(uid, sid, "Brouillon généré automatiquement",
                      f"Le workflow « {wf['name']} » a rédigé : {draft.title}. Relisez-le dans Brouillons.", wf)
    except HTTPException as exc:
        detail = {"action": "generate_draft", "ok": False, "detail": str(exc.detail)}
        await _notify(uid, sid, "Échec de génération du brouillon",
                      f"Le workflow « {wf['name']} » n'a pas pu générer le brouillon : {exc.detail}", wf)
    except Exception as exc:
        logger.exception("Background workflow draft generation failed (wf %s)", wf["id"])
        detail = {"action": "generate_draft", "ok": False, "detail": str(exc)[:200]}
        await _notify(uid, sid, "Échec de génération du brouillon",
                      f"Le workflow « {wf['name']} » n'a pas pu générer le brouillon.", wf)
    await db.workflows.update_one({"id": wf["id"]}, {"$push": {"last_result.actions_results": detail}})


async def _run_workflow(wf: dict, force: bool = False) -> dict:
    fired, reason, context = await _evaluate_workflow_trigger(wf)
    result = {"fired": fired, "reason": reason, "actions_results": []}
    if fired:
        result["actions_results"] = await _execute_workflow_actions(wf, reason, context, background=force)
    update = {
        "last_run_at": now_iso(),
        "last_result": result,
    }
    if fired:
        update["last_fired_at"] = now_iso()
        update["last_fired_date"] = datetime.now(timezone.utc).date().isoformat()
    await db.workflows.update_one({"id": wf["id"]}, {"$set": update})
    return result


async def _workflow_processor_job():
    """Scheduler job — hourly, evaluates enabled workflows (max once fired per day each)."""
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        wfs = await db.workflows.find({"enabled": True}, {"_id": 0}).to_list(500)
        for wf in wfs:
            if wf.get("last_fired_date") == today:
                continue
            try:
                res = await _run_workflow(wf)
                if res["fired"]:
                    logger.info("Workflow %s fired: %s", wf["id"], res["reason"])
            except Exception:
                logger.exception("Workflow %s evaluation failed", wf["id"])
    except Exception as exc:
        logger.error("Workflow processor error: %s", exc)


@api.get("/workflows")
async def list_workflows(site_id: Optional[str] = None, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        q["site_id"] = site_id
    return await db.workflows.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/workflows")
async def create_workflow(payload: WorkflowCreate, user=Depends(get_current_user)):
    await _get_user_site(payload.site_id, user)
    if not payload.actions:
        raise HTTPException(400, "Sélectionnez au moins une action.")
    wf = {
        "id": gen_id(),
        "user_id": user["id"],
        **payload.model_dump(),
        "created_at": now_iso(),
        "last_run_at": None,
        "last_fired_at": None,
        "last_fired_date": None,
        "last_result": None,
    }
    await db.workflows.insert_one(wf)
    wf.pop("_id", None)
    return wf


@api.patch("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, payload: WorkflowUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "actions" in updates and not updates["actions"]:
        raise HTTPException(400, "Sélectionnez au moins une action.")
    res = await db.workflows.update_one({"id": workflow_id, "user_id": user["id"]}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, "Workflow introuvable")
    return await db.workflows.find_one({"id": workflow_id}, {"_id": 0})


@api.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user=Depends(get_current_user)):
    res = await db.workflows.delete_one({"id": workflow_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Workflow introuvable")
    return {"ok": True}


@api.post("/workflows/{workflow_id}/run")
async def run_workflow_now(workflow_id: str, user=Depends(get_current_user)):
    wf = await db.workflows.find_one({"id": workflow_id, "user_id": user["id"]}, {"_id": 0})
    if not wf:
        raise HTTPException(404, "Workflow introuvable")
    return await _run_workflow(wf, force=True)


class NotificationsReadRequest(BaseModel):
    ids: Optional[List[str]] = None
    all: bool = False


@api.get("/notifications")
async def list_notifications(unread_only: bool = False, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if unread_only:
        q["read"] = False
    items = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"notifications": items, "unread_count": unread}


@api.post("/notifications/read")
async def mark_notifications_read(payload: NotificationsReadRequest, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if not payload.all:
        if not payload.ids:
            raise HTTPException(400, "Fournissez des ids ou all=true.")
        q["id"] = {"$in": payload.ids}
    res = await db.notifications.update_many(q, {"$set": {"read": True}})
    return {"ok": True, "updated": res.modified_count}


