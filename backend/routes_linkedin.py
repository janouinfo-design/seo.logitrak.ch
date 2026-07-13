from datetime import datetime
from datetime import timedelta
from datetime import timezone
from fastapi import Depends
from fastapi import HTTPException
import httpx
import jwt
import os
from app_core import EMERGENT_LLM_KEY, JWT_ALGORITHM, JWT_SECRET, api, db, dec, enc, get_current_user, logger, now_iso

# ---------------------------------------------------------------------------
# LinkedIn OAuth 2.0 + UGC Post API (auto-posting articles)
# ---------------------------------------------------------------------------
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = os.environ.get("LINKEDIN_REDIRECT_URI", "")
LINKEDIN_SCOPES = "openid profile email w_member_social"


@api.get("/linkedin/status")
async def linkedin_status(user=Depends(get_current_user)):
    doc = await db.users.find_one({"id": user["id"]}, {"linkedin": 1, "_id": 0})
    li = (doc or {}).get("linkedin") or {}
    configured = bool(LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET and LINKEDIN_REDIRECT_URI)
    return {
        "server_configured": configured,
        "connected": bool(li.get("access_token")),
        "name": li.get("name"),
        "email": li.get("email"),
        "expires_at": li.get("expires_at"),
        "member_urn": li.get("member_urn"),
    }


@api.get("/linkedin/login")
async def linkedin_login(user=Depends(get_current_user)):
    if not (LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET and LINKEDIN_REDIRECT_URI):
        raise HTTPException(503, "LinkedIn OAuth non configuré côté serveur.")
    state_token = jwt.encode(
        {"sub": user["id"], "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "state": state_token,
        "scope": LINKEDIN_SCOPES,
    }
    from urllib.parse import urlencode
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"
    return {"authorization_url": auth_url}


@api.get("/linkedin/oauth/callback")
async def linkedin_callback(code: str, state: str):
    from fastapi.responses import RedirectResponse
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload["sub"]
    except Exception as exc:
        raise HTTPException(400, f"État OAuth invalide ou expiré: {exc}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Exchange code for token
        token_resp = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": LINKEDIN_REDIRECT_URI,
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(502, f"LinkedIn token exchange failed: {token_resp.text[:300]}")
        tok = token_resp.json()
        access_token = tok["access_token"]
        expires_in = int(tok.get("expires_in", 5184000))  # default 60d
        refresh_token = tok.get("refresh_token")

        # Get user info via OpenID Connect userinfo
        ui_resp = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if ui_resp.status_code != 200:
            raise HTTPException(502, f"LinkedIn userinfo failed: {ui_resp.text[:300]}")
        ui = ui_resp.json()
        member_id = ui.get("sub")  # OpenID Connect "sub" is the member's URN-id
        member_urn = f"urn:li:person:{member_id}"

    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "linkedin": {
                "access_token": enc(access_token),
                "refresh_token": enc(refresh_token) if refresh_token else None,
                "expires_at": expires_at,
                "member_id": member_id,
                "member_urn": member_urn,
                "name": ui.get("name"),
                "email": ui.get("email"),
                "connected_at": now_iso(),
            }
        }},
    )

    # Redirect to frontend
    frontend_url = LINKEDIN_REDIRECT_URI.replace("/api/linkedin/oauth/callback", "/drafts?linkedin=connected")
    return RedirectResponse(url=frontend_url)


@api.post("/linkedin/disconnect")
async def linkedin_disconnect(user=Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"linkedin": ""}})
    return {"ok": True}


async def _generate_linkedin_post_text(draft: dict) -> str:
    """Use Claude to generate a professional LinkedIn post (max 1300 chars) from the article."""
    title = draft.get("title", "")
    body = (draft.get("body_markdown") or "")[:3000]
    prompt = f"""Génère un post LinkedIn professionnel et engageant en français à partir de cet article SEO. Le post doit :
- Faire 800-1300 caractères max (LinkedIn cap à 3000 mais 800-1300 est optimal)
- Démarrer par une accroche forte (statistique, question ou affirmation contre-intuitive)
- Inclure 3-4 points clés en bullet points avec emojis pertinents (sobres, B2B)
- Finir par un call-to-action invitant à lire l'article complet
- Inclure 3-5 hashtags pertinents à la fin
- NE PAS inclure l'URL (elle sera ajoutée séparément comme link preview)

ARTICLE TITRE: {title}
ARTICLE EXTRAIT: {body}

Retourne UNIQUEMENT le texte du post, rien d'autre."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"li-{draft.get('id')}", system_message="Tu es un expert en copywriting LinkedIn B2B.").with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=prompt))
        return (resp or "").strip().strip('"').strip("'")
    except Exception as exc:
        logger.warning("LinkedIn post text generation failed: %s", exc)
        # Fallback
        return f"📢 Nouveau guide SEO : {title}\n\nDécouvrez nos conseils pour optimiser votre activité.\n\n#SEO #Suisse #Logirent"


async def _get_linkedin_access_token(user_id: str) -> tuple[str, str]:
    """Return (access_token, member_urn) for a user, refreshing the token if needed. Returns plaintext token."""
    udoc = await db.users.find_one({"id": user_id}, {"linkedin": 1, "_id": 0})
    li = (udoc or {}).get("linkedin") or {}
    if not li.get("access_token"):
        raise HTTPException(401, "LinkedIn non connecté.")
    access_token = dec(li["access_token"])
    member_urn = li.get("member_urn")
    if not member_urn:
        raise HTTPException(400, "LinkedIn member URN manquant. Reconnectez-vous.")
    # Refresh if expires within 24h
    expires_at = li.get("expires_at")
    needs_refresh = False
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp <= datetime.now(timezone.utc) + timedelta(hours=24):
                needs_refresh = True
        except Exception:
            pass
    if needs_refresh and li.get("refresh_token"):
        refresh_token = dec(li["refresh_token"])
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": LINKEDIN_CLIENT_ID,
                    "client_secret": LINKEDIN_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code == 200:
                tok = r.json()
                access_token = tok["access_token"]
                new_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 5184000)))).isoformat()
                update = {"linkedin.access_token": enc(access_token), "linkedin.expires_at": new_expires_at}
                if tok.get("refresh_token"):
                    update["linkedin.refresh_token"] = enc(tok["refresh_token"])
                await db.users.update_one({"id": user_id}, {"$set": update})
                logger.info("LinkedIn token refreshed for user %s", user_id)
            else:
                logger.warning("LinkedIn refresh failed (%s): %s", r.status_code, r.text[:200])
    return access_token, member_urn


@api.post("/drafts/{draft_id}/publish-linkedin")
async def publish_draft_to_linkedin(draft_id: str, user=Depends(get_current_user)):
    """Generate a LinkedIn post from the draft and publish via UGC Posts API."""
    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")

    access_token, member_urn = await _get_linkedin_access_token(user["id"])
    post_text = await _generate_linkedin_post_text(d)
    article_url = d.get("github_public_url")

    share_content = {"shareCommentary": {"text": post_text}, "shareMediaCategory": "NONE"}
    if article_url:
        share_content["shareMediaCategory"] = "ARTICLE"
        share_content["media"] = [{"status": "READY", "originalUrl": article_url}]

    body = {
        "author": member_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code not in (200, 201, 202):
            if resp.status_code == 401:
                raise HTTPException(401, "Token LinkedIn expiré ou révoqué. Reconnectez votre compte LinkedIn.")
            raise HTTPException(502, f"LinkedIn UGC post error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        post_urn = data.get("id") or data.get("urn") or ""

    public_post_url = f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else None
    await db.drafts.update_one(
        {"id": draft_id},
        {"$set": {
            "linkedin_post_urn": post_urn,
            "linkedin_post_url": public_post_url,
            "linkedin_posted_at": now_iso(),
        }},
    )
    return {
        "ok": True,
        "post_urn": post_urn,
        "post_url": public_post_url,
        "post_text": post_text,
        "article_url": article_url,
    }


