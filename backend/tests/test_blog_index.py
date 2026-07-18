import asyncio
import base64
import json
import re
from unittest.mock import AsyncMock, MagicMock

import routes_publish as rp

IDX_HTML = """<main>
      <div class="articles" id="articles">
        <div class="empty">
          Aucun article publié pour le moment.
        </div>
      </div>
    </main>"""


class Resp:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._p = payload or {}

    def json(self):
        return self._p


def test_public_page_url_includes_folder():
    site = {"github_public_url": "https://blog.logirent.ch", "github_folder": "blog"}
    assert rp._github_public_page_url(site, "a") == "https://blog.logirent.ch/blog/a.html"
    site2 = {"github_public_url": "https://blog.logirent.ch/blog", "github_folder": "blog"}
    assert rp._github_public_page_url(site2, "a") == "https://blog.logirent.ch/blog/a.html"
    site3 = {"github_public_url": "https://s.ch", "github_folder": "public/blog"}
    assert rp._github_public_page_url(site3, "a") == "https://s.ch/blog/a.html"
    assert rp._github_public_page_url({"github_public_url": "https://s.ch"}, "a") == "https://s.ch/a.html"
    assert rp._github_public_page_url({}, "a") is None


def test_update_blog_index_injects_cards(monkeypatch):
    client = MagicMock()
    existing_index = base64.b64encode(IDX_HTML.encode()).decode()
    client.get = AsyncMock(side_effect=[Resp(404), Resp(200, {"sha": "abc", "content": existing_index})])
    put_calls = []

    async def fake_put(client, token, owner, repo, path, branch, msg, content, sha):
        put_calls.append((path, content))
        return {"commit_sha": "s"}

    monkeypatch.setattr(rp, "_github_put_file", fake_put)
    draft = {"title": "Mon Titre <Test>", "meta_description": "Ma description", "cover_image_url": "http://img"}
    res = asyncio.get_event_loop().run_until_complete(
        rp._github_update_blog_index(client, "t", "o", "r", "main", draft, "mon-titre", "https://blog.logirent.ch/blog/mon-titre.html")
    )
    assert res["action"] == "index_updated" and res["count"] == 1
    assert [p for p, _ in put_calls] == ["articles.json", "index.html"]
    aj = json.loads(put_calls[0][1])
    assert aj[0]["slug"] == "mon-titre"
    assert aj[0]["url"].endswith("/blog/mon-titre.html")
    new_idx = put_calls[1][1]
    assert "Mon Titre &lt;Test&gt;" in new_idx
    assert "empty" not in new_idx


def test_sitemap_stale_entry_removed():
    slug = "excel-vs-test"
    xml = (
        "<urlset>\n"
        "  <url>\n    <loc>https://blog.logirent.ch/autre-page.html</loc>\n    <lastmod>2026-06-01</lastmod>\n  </url>\n"
        "  <url>\n    <loc>https://blog.logirent.ch/excel-vs-test.html</loc>\n    <lastmod>2026-06-15</lastmod>\n  </url>\n"
        "</urlset>"
    )
    stale = re.compile(r"\s*<url>(?:(?!</url>).)*?/" + re.escape(slug) + r"\.html</loc>(?:(?!</url>).)*?</url>", re.DOTALL)
    cleaned = stale.sub("", xml)
    assert "excel-vs-test.html" not in cleaned
    assert "autre-page.html" in cleaned
