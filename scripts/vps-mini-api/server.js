/**
 * LOGI SEO Booster — VPS Mini-API
 * ---------------------------------
 * Petite API Express à déployer sur votre VPS pour recevoir les contenus SEO
 * envoyés depuis LOGI SEO Booster et les écrire sous forme de fichiers JSON
 * (ou HTML) consommables par votre site Logirent / Logitime.
 *
 * Endpoints :
 *   GET  /api/health         → vérifie que l'API est en ligne
 *   POST /api/seo/publish    → reçoit un contenu (requiert Bearer token)
 *   GET  /api/seo/list       → liste les contenus publiés
 *   GET  /api/seo/:slug      → récupère un contenu par slug
 *
 * Sécurité : Bearer token partagé (variable d'env SEO_API_TOKEN).
 *
 * Déploiement rapide :
 *   1. scp -r vps-mini-api/ user@votre-vps:/opt/logi-seo-api/
 *   2. cd /opt/logi-seo-api && npm install
 *   3. cp .env.example .env && nano .env  (mettre un token aléatoire long)
 *   4. node server.js  (ou via PM2 / systemd, voir README.md)
 *   5. nginx reverse proxy vers ce port (3001 par défaut)
 */

import express from "express";
import cors from "cors";
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { marked } from "marked";
import "dotenv/config";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.PORT || 3001;
const TOKEN = process.env.SEO_API_TOKEN;
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "data");

if (!TOKEN) {
  console.error("[FATAL] SEO_API_TOKEN manquant dans .env — refus de démarrer.");
  process.exit(1);
}

await fs.mkdir(DATA_DIR, { recursive: true });

const app = express();
app.use(cors());
app.use(express.json({ limit: "5mb" }));

// --- Middleware: bearer auth -----------------------------------------------
function requireToken(req, res, next) {
  const h = req.headers.authorization || "";
  if (!h.startsWith("Bearer ") || h.slice(7) !== TOKEN) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
}

function slugify(str) {
  return (str || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

// --- Public endpoints ------------------------------------------------------
app.get("/api/health", (req, res) => {
  res.json({ ok: true, app: "logi-seo-vps-mini-api", version: "1.0.0" });
});

app.get("/api/seo/list", async (req, res) => {
  try {
    const files = await fs.readdir(DATA_DIR);
    const items = [];
    for (const f of files.filter((x) => x.endsWith(".json"))) {
      const raw = await fs.readFile(path.join(DATA_DIR, f), "utf-8");
      const d = JSON.parse(raw);
      items.push({
        id: d.id,
        slug: d.slug,
        title: d.title,
        meta_title: d.meta_title,
        meta_description: d.meta_description,
        content_type: d.content_type,
        published_at: d.published_at,
      });
    }
    items.sort((a, b) => (b.published_at || "").localeCompare(a.published_at || ""));
    res.json({ items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/seo/:slug", async (req, res) => {
  try {
    const filename = path.join(DATA_DIR, `${req.params.slug}.json`);
    const raw = await fs.readFile(filename, "utf-8");
    const d = JSON.parse(raw);
    res.json(d);
  } catch (err) {
    res.status(404).json({ error: "Not found" });
  }
});

// --- Protected: publish ----------------------------------------------------
app.post("/api/seo/publish", requireToken, async (req, res) => {
  try {
    const body = req.body || {};
    const id = crypto.randomUUID();
    const slug = slugify(body.title || id);
    const doc = {
      id,
      slug,
      title: body.title || "",
      meta_title: body.meta_title || body.title || "",
      meta_description: body.meta_description || "",
      content_type: body.content_type || "article",
      body_markdown: body.body_markdown || "",
      body_html: marked.parse(body.body_markdown || ""),
      keywords: body.keywords || [],
      faq: body.faq || [],
      source: body.source || "unknown",
      published_at: new Date().toISOString(),
    };
    await fs.writeFile(
      path.join(DATA_DIR, `${slug}.json`),
      JSON.stringify(doc, null, 2),
      "utf-8"
    );
    console.log(`[publish] ${slug} (${doc.title})`);
    res.status(201).json({ id, slug, url_path: `/blog/${slug}` });
  } catch (err) {
    console.error("[publish] error:", err);
    res.status(500).json({ error: err.message });
  }
});

// --- Optional: serve published content as HTML (basic preview) -------------
app.get("/blog/:slug", async (req, res) => {
  try {
    const filename = path.join(DATA_DIR, `${req.params.slug}.json`);
    const raw = await fs.readFile(filename, "utf-8");
    const d = JSON.parse(raw);
    const faqHtml = (d.faq || [])
      .map((q) => `<details><summary><b>${q.question}</b></summary><p>${q.answer}</p></details>`)
      .join("");
    res.send(`<!doctype html>
<html lang="fr"><head>
  <meta charset="utf-8">
  <title>${d.meta_title}</title>
  <meta name="description" content="${d.meta_description}">
</head><body style="font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.6">
  <h1>${d.title}</h1>
  ${d.body_html}
  ${faqHtml ? `<h2>FAQ</h2>${faqHtml}` : ""}
</body></html>`);
  } catch {
    res.status(404).send("Not found");
  }
});

app.listen(PORT, () => {
  console.log(`✓ LOGI SEO mini-API démarrée sur le port ${PORT}`);
  console.log(`  Data dir : ${DATA_DIR}`);
  console.log(`  Token    : ${TOKEN.slice(0, 6)}…${TOKEN.slice(-3)}`);
});
