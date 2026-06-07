"""Generate the LOGI SEO Booster user guide as a PDF."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, ListFlowable, ListItem,
)
from reportlab.pdfgen import canvas

OUT = "/app/frontend/public/guide-logi-seo-booster.pdf"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

KLEIN = colors.HexColor("#002FA7")
KLEIN_DARK = colors.HexColor("#001D6B")
TEXT = colors.HexColor("#020617")
MUTED = colors.HexColor("#64748B")
BG = colors.HexColor("#F8FAFC")
BORDER = colors.HexColor("#E2E8F0")
SUCCESS = colors.HexColor("#16A34A")
WARNING = colors.HexColor("#D97706")
DANGER = colors.HexColor("#DC2626")

styles = getSampleStyleSheet()

h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=22, textColor=TEXT, spaceAfter=14, spaceBefore=4, leading=26)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=15, textColor=KLEIN, spaceAfter=8, spaceBefore=18, leading=20)
h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                    fontSize=11.5, textColor=TEXT, spaceAfter=4, spaceBefore=10, leading=16)
body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=10, textColor=TEXT, leading=15, spaceAfter=6, alignment=TA_JUSTIFY)
small = ParagraphStyle("Small", parent=body, fontSize=9, textColor=MUTED, leading=13)
overline = ParagraphStyle("Overline", parent=body, fontName="Helvetica-Bold",
                          fontSize=8, textColor=MUTED, spaceAfter=4)
mono = ParagraphStyle("Mono", parent=body, fontName="Courier",
                      fontSize=9.5, textColor=TEXT, backColor=BG, leading=14,
                      borderPadding=6, leftIndent=0, rightIndent=0)


def cover_page(canv, doc):
    canv.saveState()
    width, height = A4
    # Top blue band
    canv.setFillColor(KLEIN)
    canv.rect(0, height - 6 * cm, width, 6 * cm, fill=1, stroke=0)
    # Logo block
    canv.setFillColor(colors.white)
    canv.setFont("Helvetica-Bold", 36)
    canv.drawString(2.5 * cm, height - 3.2 * cm, "LOGI")
    canv.setFont("Helvetica-Bold", 10)
    canv.setFillColorRGB(1, 1, 1, alpha=0.85)
    canv.drawString(2.5 * cm, height - 3.8 * cm, "SEO BOOSTER")
    # Subtitle
    canv.setFillColor(TEXT)
    canv.setFont("Helvetica-Bold", 26)
    canv.drawString(2.5 * cm, height - 8.5 * cm, "Guide d'utilisation")
    canv.setFont("Helvetica", 12)
    canv.setFillColor(MUTED)
    canv.drawString(2.5 * cm, height - 9.3 * cm,
                    "Audit · Mots-clés · Optimiseur · Génération de contenu · Publication")
    # Tagline box
    canv.setFillColor(BG)
    canv.setStrokeColor(BORDER)
    canv.rect(2.5 * cm, 7 * cm, width - 5 * cm, 2.4 * cm, fill=1, stroke=1)
    canv.setFillColor(TEXT)
    canv.setFont("Helvetica-Bold", 11)
    canv.drawString(3.2 * cm, 8.6 * cm, "Atteignez la première page Google sur Logirent et Logitime")
    canv.setFont("Helvetica", 9.5)
    canv.setFillColor(MUTED)
    canv.drawString(3.2 * cm, 8.0 * cm, "Une plateforme SaaS pour analyser, générer et optimiser le contenu SEO")
    canv.drawString(3.2 * cm, 7.6 * cm, "de vos sites Logirent.ch, Logitime.ch et de vos sites Wix.")
    # Footer
    canv.setFillColor(MUTED)
    canv.setFont("Helvetica", 8.5)
    canv.drawString(2.5 * cm, 2 * cm, "Version 1.0 — Février 2026")
    canv.drawRightString(width - 2.5 * cm, 2 * cm, "Édition Logirent / Logitime")
    canv.setStrokeColor(KLEIN)
    canv.setLineWidth(2)
    canv.line(2.5 * cm, 1.7 * cm, width - 2.5 * cm, 1.7 * cm)
    canv.restoreState()


def page_chrome(canv, doc):
    canv.saveState()
    width, _ = A4
    # Header
    canv.setStrokeColor(BORDER)
    canv.setLineWidth(0.5)
    canv.line(2 * cm, A4[1] - 1.5 * cm, width - 2 * cm, A4[1] - 1.5 * cm)
    canv.setFillColor(KLEIN)
    canv.setFont("Helvetica-Bold", 9)
    canv.drawString(2 * cm, A4[1] - 1.2 * cm, "LOGI SEO BOOSTER")
    canv.setFillColor(MUTED)
    canv.setFont("Helvetica", 9)
    canv.drawRightString(width - 2 * cm, A4[1] - 1.2 * cm, "Guide d'utilisation")
    # Footer
    canv.line(2 * cm, 1.5 * cm, width - 2 * cm, 1.5 * cm)
    canv.setFillColor(MUTED)
    canv.setFont("Helvetica", 8.5)
    canv.drawString(2 * cm, 1.1 * cm, f"Page {doc.page - 1}")
    canv.drawRightString(width - 2 * cm, 1.1 * cm, "logi-seo-booster.app")
    canv.restoreState()


def callout(text, kind="info"):
    color_map = {
        "info": (KLEIN, colors.HexColor("#EFF6FF")),
        "warning": (WARNING, colors.HexColor("#FEF3C7")),
        "success": (SUCCESS, colors.HexColor("#DCFCE7")),
        "danger": (DANGER, colors.HexColor("#FEE2E2")),
    }
    border_color, bg_color = color_map.get(kind, color_map["info"])
    tbl = Table([[Paragraph(text, body)]], colWidths=[16.5 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBEFORE", (0, 0), (0, -1), 3, border_color),
    ]))
    return tbl


def step_box(num, title, content_paragraphs):
    """A boxed step with a number badge."""
    num_cell = Paragraph(f'<font color="#FFFFFF" size="14"><b>{num}</b></font>', body)
    title_p = Paragraph(f'<b>{title}</b>', h3)
    inner = [title_p] + content_paragraphs
    tbl = Table([[
        Table([[num_cell]], colWidths=[1.1 * cm], rowHeights=[1.1 * cm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), KLEIN),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])),
        inner,
    ]], colWidths=[1.4 * cm, 15.1 * cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def kv_table(rows):
    data = [[Paragraph(f"<b>{k}</b>", body), Paragraph(v, body)] for k, v in rows]
    tbl = Table(data, colWidths=[4.5 * cm, 12 * cm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND", (0, 0), (0, -1), BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def bullet(items):
    return ListFlowable(
        [ListItem(Paragraph(it, body), leftIndent=0, value="•") for it in items],
        bulletType="bullet", leftIndent=14, bulletColor=KLEIN, bulletFontSize=9,
    )


# ---------------------------------------------------------------------------
# Build the document
# ---------------------------------------------------------------------------
doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=2 * cm, rightMargin=2 * cm,
    topMargin=2.2 * cm, bottomMargin=2 * cm,
    title="Guide d'utilisation — LOGI SEO Booster",
    author="LOGI SEO Booster",
)

story = []

# --- Cover (rendered via onFirstPage). Skip first page by issuing only a PageBreak ---
story.append(Spacer(1, 1))  # tiny spacer just to enter the doc
story.append(PageBreak())

# --- Table of contents ---
story.append(Paragraph("Sommaire", h1))
story.append(Spacer(1, 6))
toc = [
    ("1. Présentation", "3"),
    ("2. Accéder à l'application", "3"),
    ("3. Connecter vos sites (Logirent, Logitime, Wix)", "4"),
    ("4. Audit SEO automatique", "6"),
    ("5. Recherche IA de mots-clés", "7"),
    ("6. Optimiseur de pages existantes", "9"),
    ("7. Générateur de contenu IA", "10"),
    ("8. Brouillons : relecture, versions, rollback", "11"),
    ("9. Publication sur Wix ou export", "12"),
    ("10. Suivi de performance (Search Console)", "13"),
    ("11. Astuces avancées & raccourcis", "13"),
    ("12. FAQ & dépannage", "14"),
]
toc_tbl = Table([[Paragraph(t, body), Paragraph(p, body)] for t, p in toc],
                colWidths=[14 * cm, 2 * cm])
toc_tbl.setStyle(TableStyle([
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("LINEBELOW", (0, 0), (-1, -2), 0.3, BORDER),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(toc_tbl)
story.append(PageBreak())

# --- 1. Présentation ---
story.append(Paragraph("1. Présentation", h1))
story.append(Paragraph(
    "<b>LOGI SEO Booster</b> est une plateforme SaaS conçue pour faire grimper "
    "vos sites — en priorité <b>Logirent.ch</b> et <b>Logitime.ch</b> — dans les "
    "résultats Google et dans les moteurs IA (ChatGPT, Gemini, Perplexity, Google "
    "AI Overviews).", body))
story.append(Paragraph(
    "L'application combine 4 piliers : <b>audit SEO automatique</b>, <b>recherche "
    "de mots-clés assistée par IA</b>, <b>optimisation des pages existantes</b>, "
    "et <b>génération de contenu</b> (articles, pages locales, FAQ) avec Claude "
    "Sonnet 4.5. Vous validez chaque contenu avant publication — aucune mise en "
    "ligne automatique.", body))
story.append(Spacer(1, 4))
story.append(Paragraph("Ce que l'app fait pour vous", h3))
story.append(bullet([
    "Scanne vos vraies pages publiques (logirent.ch, logitime.ch) pour détecter "
    "tous les défauts SEO : titres manquants, méta absentes, H1/H2 mal "
    "structurés, images sans <i>alt</i>, contenu trop court, SPA non-indexable.",
    "Identifie les mots-clés à fort potentiel par intention (locale, "
    "informationnelle, transactionnelle, marque) avec niveau de difficulté et "
    "priorité.",
    "Compare votre titre / méta / H1 actuels à une version optimisée et la "
    "transforme en brouillon prêt à publier en 1 clic.",
    "Génère des articles, pages locales, FAQ rédigés <b>spécifiquement</b> pour "
    "ranker en première page Google et apparaître dans les AI Overviews.",
    "Conserve l'historique des publications, des versions, et permet le "
    "rollback à tout moment.",
]))

# --- 2. Accès ---
story.append(Paragraph("2. Accéder à l'application", h2))
story.append(kv_table([
    ("URL d'accès", '<font color="#002FA7">https://content-logi-pro.preview.emergentagent.com</font>'),
    ("Email démo", "<font name='Courier'>demo@logirent.fr</font>"),
    ("Mot de passe démo", "<font name='Courier'>demo1234</font>"),
    ("Modèle IA", "Claude Sonnet 4.5 (Anthropic) via Emergent Universal Key"),
]))
story.append(Spacer(1, 6))
story.append(callout(
    "<b>Compte démo prêt à l'emploi :</b> les sites <b>logirent.ch</b> et "
    "<b>logitime.ch</b> sont déjà connectés sur le compte démo. Vous pouvez "
    "lancer un audit ou une optimisation immédiatement.", "info"))
story.append(Spacer(1, 6))
story.append(Paragraph("Créer votre propre compte", h3))
story.append(bullet([
    "Allez sur <b>/register</b>, renseignez nom, email pro, mot de passe (≥ 6 caractères).",
    "Vous êtes connecté automatiquement et redirigé vers la page <b>Sites</b>.",
]))
story.append(PageBreak())

# --- 3. Connecter ---
story.append(Paragraph("3. Connecter vos sites", h1))
story.append(Paragraph(
    "L'app supporte <b>deux types de connexion</b>, que vous pouvez combiner : "
    "URL publique (idéal pour Logirent / Logitime hébergés sur Emergent) et API "
    "Wix (pour vos autres sites Wix).", body))

story.append(Paragraph("Option A — Sites Emergent (logirent.ch & logitime.ch)", h2))
story.append(step_box(1, "Ajout en 1 clic", [
    Paragraph("Page <b>Sites</b> → bouton orange <b>« Ajouter logirent.ch + logitime.ch »</b>. "
              "Aucune clé API requise — l'app scanne vos pages publiques par HTTP.", body),
]))
story.append(Spacer(1, 4))
story.append(step_box(2, "Vérification", [
    Paragraph("Les deux sites apparaissent dans la grille avec le label "
              "<b>URL publique</b>. Le sélecteur en haut à gauche permet de "
              "basculer entre Logirent et Logitime.", body),
]))
story.append(Spacer(1, 4))
story.append(callout(
    "<b>Découverte importante :</b> lors du premier audit, Logirent et Logitime "
    "vont remonter en <b>CRITIQUE</b> la mention <i>« Page rendue côté client "
    "(SPA) — Google et les IA voient un HTML quasi vide »</i>. C'est le point "
    "n°1 à corriger pour ranker. Solutions possibles : activer le SSR/SSG sur "
    "Emergent, ou ajouter un crawler Playwright à l'app pour rendre le JS.",
    "warning"))

story.append(Spacer(1, 8))
story.append(Paragraph("Option B — Vos autres sites Wix", h2))
story.append(step_box(1, "Générer une clé API Wix", [
    Paragraph("Wix → <b>Settings</b> → <b>Headless Settings</b> → "
              "<b>API keys</b> → créer une clé avec les permissions "
              "<i>Blog</i> et <i>Site Pages</i>.", body),
    Paragraph("Notez votre <b>API Key</b>, votre <b>Site ID</b> et votre "
              "<b>Account ID</b>.", small),
]))
story.append(Spacer(1, 4))
story.append(step_box(2, "Connecter dans l'app", [
    Paragraph("Page <b>Sites</b> → <b>Ajouter un site</b> → choisir le type "
              "<b>« Wix (API) »</b> → remplir Site ID, Account ID, API Key.", body),
    Paragraph("La clé est stockée côté serveur uniquement.", small),
]))
story.append(PageBreak())

# --- 4. Audit ---
story.append(Paragraph("4. Audit SEO automatique", h1))
story.append(Paragraph(
    "L'audit scanne automatiquement toutes les pages de votre site et détecte "
    "les défauts qui pénalisent votre référencement.", body))
story.append(Paragraph("Comment lancer un audit", h3))
story.append(step_box(1, "Sélectionner le site", [
    Paragraph("Cliquez sur le sélecteur en haut à gauche → choisissez "
              "<b>Logirent</b> ou <b>Logitime</b>.", body),
]))
story.append(step_box(2, "Lancer le scan", [
    Paragraph("Menu <b>Audit SEO</b> → bouton <b>« Lancer un audit »</b>. "
              "Le scan prend 10-30 secondes selon le nombre de pages.", body),
]))
story.append(step_box(3, "Lire le rapport", [
    Paragraph("Vous obtenez : un <b>score global /100</b>, le nombre de pages "
              "analysées, le décompte des problèmes par sévérité, et la liste "
              "détaillée avec recommandation concrète pour chaque issue.", body),
]))
story.append(Spacer(1, 6))
story.append(Paragraph("Types de problèmes détectés", h3))
issues = [
    ["Sévérité", "Catégorie", "Exemple de détection"],
    ["CRITIQUE", "Rendu côté client", "Page SPA — HTML quasi vide pour Google"],
    ["CRITIQUE", "Méta description", "Méta description absente"],
    ["CRITIQUE", "Structure H1", "Aucun H1 détecté"],
    ["IMPORTANT", "Titre SEO", "Titre trop court (< 30 caractères)"],
    ["IMPORTANT", "Images", "Images sans attribut alt"],
    ["IMPORTANT", "Contenu", "Page < 300 mots"],
    ["MINEUR", "URL", "URL non optimisée"],
    ["MINEUR", "Structure H2", "Aucun H2"],
]
sev_tbl = Table(issues, colWidths=[3 * cm, 4.5 * cm, 9 * cm])
sev_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), KLEIN),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("TEXTCOLOR", (0, 1), (0, 3), DANGER),
    ("TEXTCOLOR", (0, 4), (0, 6), WARNING),
    ("TEXTCOLOR", (0, 7), (0, 8), colors.HexColor("#0EA5E9")),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
]))
story.append(sev_tbl)
story.append(PageBreak())

# --- 5. Mots-clés ---
story.append(Paragraph("5. Recherche IA de mots-clés", h1))
story.append(Paragraph(
    "Identifiez les mots-clés à fort potentiel pour atteindre la première "
    "page Google, classés par <b>intention de recherche</b>.", body))
story.append(Spacer(1, 4))
story.append(Paragraph("4 clusters générés", h3))
clusters = [
    ["Cluster", "Description", "Exemple"],
    ["LOCALE", "Recherche avec ville/zone", "location voiture genève"],
    ["INFORMATIONNELLE", "Question / besoin d'info", "comment louer une voiture"],
    ["TRANSACTIONNELLE", "Intention d'achat", "réserver véhicule pas cher"],
    ["NAVIGATIONNELLE", "Recherche de marque", "avis logirent"],
]
ctbl = Table(clusters, colWidths=[3.5 * cm, 6 * cm, 7 * cm])
ctbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), KLEIN),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
]))
story.append(ctbl)
story.append(Spacer(1, 8))
story.append(Paragraph("Lancer une recherche", h3))
story.append(step_box(1, "Saisir la thématique", [
    Paragraph("Menu <b>Mots-clés</b> → entrez :", body),
    bullet([
        "<b>Thématique</b> (obligatoire) : ex. « location voitures courte durée »",
        "<b>Ville / zone</b> : ex. « Genève » ou « Suisse romande »",
        "<b>Concurrents</b> (optionnel) : séparés par virgules",
    ]),
]))
story.append(step_box(2, "Analyser & sélectionner", [
    Paragraph("Cliquez <b>« Lancer la recherche IA »</b> (15-30 s). Pour chaque "
              "mot-clé, vous voyez : <b>difficulté</b> (low/medium/high), "
              "<b>volume estimé</b>, <b>priorité</b> et une <b>justification</b>.", body),
]))
story.append(step_box(3, "Ajout en lot avec les cases à cocher", [
    Paragraph("Cochez les mots-clés un par un, ou cliquez la case "
              "<b>« Tout sélectionner »</b> par cluster ou globale. Le bouton "
              "<b>« Ajouter X mots-clés »</b> les enregistre tous en une fois "
              "dans votre liste cible.", body),
]))
story.append(Spacer(1, 4))
story.append(callout(
    "<b>Astuce :</b> ciblez en priorité la longue traîne (mots-clés de 3+ mots) "
    "avec difficulté <i>low</i> ou <i>medium</i> et priorité <i>élevée</i>. "
    "Plus facile à ranker rapidement.", "info"))
story.append(PageBreak())

# --- 6. Optimiseur ---
story.append(Paragraph("6. Optimiseur de pages existantes", h1))
story.append(Paragraph(
    "Pour chaque page existante, l'IA propose une version optimisée et "
    "affiche une comparaison <b>Avant / Après</b>.", body))
story.append(step_box(1, "Sélectionner la page à optimiser", [
    Paragraph("Menu <b>Optimiseur de pages</b> → choisissez une page dans la "
              "liste déroulante (toutes vos pages réelles sont listées).", body),
]))
story.append(step_box(2, "Mot-clé focus + ville", [
    Paragraph("Indiquez le <b>mot-clé focus</b> (ex. « logiciel location "
              "véhicules Suisse ») et la <b>ville cible</b>.", body),
]))
story.append(step_box(3, "Analyser & comparer", [
    Paragraph("Bouton <b>« Optimiser cette page »</b> (20-40 s). Trois onglets :", body),
    bullet([
        "<b>Comparaison avant/après</b> : titre, meta title, meta description "
        "et plan H2, en colonnes côte à côte (rouge barré vs vert).",
        "<b>Plan & FAQ</b> : intro « réponse courte » pour AI Overviews, plan "
        "de contenu détaillé et FAQ générée.",
        "<b>Améliorations</b> : 5-10 actions concrètes chiffrées (ex. "
        "« titre allongé de 28 → 58 caractères pour intégrer le mot-clé »).",
    ]),
]))
story.append(step_box(4, "Créer le brouillon", [
    Paragraph("Bouton <b>« Créer un brouillon prêt à publier »</b> transforme "
              "l'optimisation en brouillon éditable. Vous êtes redirigé "
              "automatiquement vers l'éditeur. L'action est <b>idempotente</b> : "
              "un seul brouillon est créé même si vous cliquez plusieurs fois.", body),
]))
story.append(PageBreak())

# --- 7. Générateur ---
story.append(Paragraph("7. Générateur de contenu IA", h1))
story.append(Paragraph(
    "Créez de nouveaux contenus SEO directement optimisés Google + IA.", body))
types_tbl = Table([
    ["Type", "Cas d'usage"],
    ["Article de blog", "Sujet thématique, ranking longue traîne"],
    ["Page locale", "Cibler une ville / région (Genève, Lausanne…)"],
    ["FAQ", "Page de questions/réponses pour AI Overviews"],
    ["Description de service", "Page produit / service commercial"],
], colWidths=[5 * cm, 11.5 * cm])
types_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), KLEIN),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
]))
story.append(types_tbl)
story.append(Spacer(1, 8))
story.append(Paragraph("Chaque contenu généré inclut", h3))
story.append(bullet([
    "<b>Titre H1</b> ciblé sur le mot-clé principal",
    "<b>Meta title</b> 50-60 caractères et <b>meta description</b> 140-160 caractères",
    "<b>Réponse courte d'introduction</b> (2-3 phrases) optimisée AI Overviews",
    "Paragraphes courts, hiérarchie H2/H3 claire",
    "<b>FAQ</b> de 4-6 questions/réponses naturelles",
    "Au moins un <b>tableau comparatif</b> ou liste structurée",
    "Données locales si une ville est précisée",
    "Densité de mots-clés naturelle (3-5 mentions du keyword principal)",
]))
story.append(Spacer(1, 4))
story.append(callout(
    "Le générateur respecte strictement la règle <b>« qualité avant quantité »</b> : "
    "contenu factuel, sans superlatifs creux, ton crédible. Aucun contenu spam.",
    "success"))
story.append(PageBreak())

# --- 8. Brouillons ---
story.append(Paragraph("8. Brouillons : relecture, versions, rollback", h1))
story.append(Paragraph(
    "Tous les contenus générés (Optimiseur + Générateur) arrivent dans la "
    "<b>Bibliothèque de brouillons</b>. Aucune publication automatique.", body))
story.append(Paragraph("Anatomie de la page brouillon", h3))
story.append(bullet([
    "<b>Onglet Éditeur</b> : édition libre du titre H1 et du contenu en Markdown",
    "<b>Onglet Aperçu</b> : rendu HTML pour visualiser le résultat final",
    "<b>Panneau latéral</b> : meta title et meta description avec <b>compteurs "
    "de caractères en temps réel</b> (vert si optimal, ambre si court, rouge si trop long)",
    "<b>Mots-clés cibles</b> et <b>FAQ</b> affichés à droite",
    "<b>Versions précédentes</b> : chaque enregistrement crée un instantané. "
    "Cliquez sur <b>« Restaurer »</b> à côté d'une version pour revenir en arrière.",
]))
story.append(Spacer(1, 8))
story.append(Paragraph("Sélection et suppression en lot", h3))
story.append(Paragraph(
    "Sur la liste des brouillons, cochez les cases à gauche (ou la case "
    "<b>« Tout sélectionner »</b> en haut) pour supprimer plusieurs brouillons "
    "en une seule action.", body))

# --- 9. Publication ---
story.append(Paragraph("9. Publication sur Wix ou export", h2))
story.append(Paragraph(
    "Depuis la page brouillon, le bouton <b>« Publier sur Wix »</b> agit "
    "différemment selon le type de site :", body))
pub_tbl = Table([
    ["Type de site", "Action du bouton « Publier »"],
    ["Wix (API)",
     "Crée un brouillon dans votre compte Wix Blog. Vous validez ensuite "
     "depuis Wix pour la mise en ligne finale."],
    ["URL publique\n(Logirent, Logitime,\nWordPress…)",
     "Marque le brouillon comme « prêt à exporter ». Vous copiez-collez le "
     "contenu et les méta dans votre CMS."],
], colWidths=[5 * cm, 11.5 * cm])
pub_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), KLEIN),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
]))
story.append(pub_tbl)
story.append(Spacer(1, 6))
story.append(callout(
    "Toutes les tentatives de publication sont enregistrées dans le menu "
    "<b>Historique</b> (date, titre, statut, Wix Draft ID si applicable).", "info"))
story.append(PageBreak())

# --- 10. Performance ---
story.append(Paragraph("10. Suivi de performance", h1))
story.append(Paragraph(
    "La page <b>Performance</b> affiche pour le site actif :", body))
story.append(bullet([
    "Impressions, clics, CTR moyen, position moyenne (28 derniers jours)",
    "Graphique temporel impressions × clics",
    "Top mots-clés avec tendance (↑ ↓ →)",
    "Recommandations automatiques basées sur les opportunités détectées",
]))
story.append(Spacer(1, 6))
story.append(callout(
    "<b>Mocked pour le MVP :</b> les données affichées sont simulées. La "
    "connexion réelle à Google Search Console (OAuth) est prévue en phase 3.",
    "warning"))

# --- 11. Astuces ---
story.append(Paragraph("11. Astuces avancées & raccourcis", h2))
story.append(bullet([
    "<b>Site actif partout</b> : le sélecteur en haut à gauche pilote toutes "
    "les pages (audit, mots-clés, optimiseur, drafts). Changez-le pour "
    "basculer entre Logirent et Logitime.",
    "<b>Cases à cocher</b> : sur Mots-clés et Brouillons, utilisez "
    "« Tout sélectionner » pour traiter plusieurs éléments en un clic.",
    "<b>Idempotence du « Créer un brouillon »</b> dans l'Optimiseur : "
    "rappuyer ne duplique pas le brouillon, vous récupérez le même.",
    "<b>Compteurs de caractères en direct</b> sur les méta : visez 50-60 pour "
    "le title et 140-160 pour la description.",
    "<b>Versions et rollback</b> : chaque sauvegarde d'un brouillon crée une "
    "version. Aucune édition n'est jamais perdue définitivement.",
    "<b>Historique des recherches mots-clés</b> : l'onglet « Historique » de "
    "la page Mots-clés rejoue n'importe quelle recherche antérieure.",
]))

# --- 12. FAQ ---
story.append(Paragraph("12. FAQ & dépannage", h2))
faq = [
    ("Pourquoi mon score d'audit est-il très bas (< 20/100) ?",
     "Vos pages sont sans doute des SPA (Single-Page Apps) rendues côté "
     "client. Google et les moteurs IA voient un HTML quasi vide. C'est "
     "LE point n°1 à corriger : activez le rendu côté serveur (SSR/SSG) "
     "ou ajoutez un service de prerendering."),
    ("L'IA met du temps à répondre, c'est normal ?",
     "Oui — Claude Sonnet 4.5 met 15-40 secondes pour une génération "
     "complète. C'est le prix d'un contenu de qualité, structuré et long."),
    ("Mes mots-clés enregistrés sont-ils suivis automatiquement ?",
     "Pas encore — le suivi de classement par mot-clé (cron quotidien sur "
     "Google) est en phase 3. Pour l'instant, votre liste cible sert de "
     "référence stratégique pour la génération et l'optimisation."),
    ("Le bouton « Publier sur Wix » ne fait rien sur Logirent/Logitime ?",
     "Normal : ces sites ne sont pas sur Wix. Le bouton marque le brouillon "
     "« prêt à exporter » — copiez le contenu dans votre CMS Emergent."),
    ("Comment supprimer un site Wix de l'app ?",
     "Page Sites → icône poubelle sur la carte du site → confirmation. Les "
     "brouillons et audits existants sont conservés."),
    ("Mes données sont-elles isolées par utilisateur ?",
     "Oui — chaque utilisateur ne voit que ses sites, audits, mots-clés, "
     "brouillons, etc. L'authentification utilise JWT et les mots de passe "
     "sont hashés avec bcrypt."),
]
for q, a in faq:
    story.append(Paragraph(f"<b>{q}</b>", h3))
    story.append(Paragraph(a, body))
    story.append(Spacer(1, 2))

# Final
story.append(Spacer(1, 14))
story.append(callout(
    "<b>Besoin d'aller plus loin ?</b> Demandez l'ajout d'un crawler Playwright "
    "(pour scanner le contenu après exécution JavaScript), du suivi de classement "
    "automatique, ou de la connexion réelle Google Search Console (OAuth).",
    "info"))

doc.build(story, onFirstPage=cover_page, onLaterPages=page_chrome)
print(f"PDF généré : {OUT}")
print(f"Taille : {os.path.getsize(OUT) / 1024:.1f} KB")
