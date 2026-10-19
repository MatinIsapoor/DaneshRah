"""DaneshRah — راهنمای فارسی زندگی دانشجویی در خارج از کشور.

Flask app: country guides, ranked Persian search, checklist, emergency numbers.

Data lives in ``data/guides.json`` (single source of truth, loaded once into
memory). Adding a new country only requires editing that JSON file — no code
changes needed. See README.md for the schema.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from flask import Flask, abort, jsonify, render_template, request
from markupsafe import Markup, escape

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Branding / constants
# ---------------------------------------------------------------------------

APP_NAME = "DaneshRah"
APP_TAGLINE_FA = "دانش‌راه — از فرودگاه تا استقرار کامل"
APP_DESCRIPTION_FA = (
    "دانش‌راه (DaneshRah): راهنمای فارسی و کاربردی زندگی دانشجویی در خارج از کشور — "
    "خرید، مسکن، بانک، سیم‌کارت و چک‌لیست روزهای اول، کشور به کشور."
)

DATA_PATH = Path(__file__).parent / "data" / "guides.json"

CATEGORY_META: dict[str, dict[str, str]] = {
    "shopping": {"icon": "cart", "label": "خرید و زندگی روزمره"},
    "housing": {"icon": "home", "label": "مسکن و اجاره‌خانه"},
    "admin": {"icon": "doc", "label": "اقامت، بیمه و امور اداری"},
    "work": {"icon": "brief", "label": "کار دانشجویی"},
    "arrival": {"icon": "compass", "label": "قدم‌های اول"},
}

# Preferred display order for region pills. Unknown regions are appended after.
REGION_ORDER = ["europe", "north_america", "asia", "oceania", "other"]

REGION_FALLBACK: dict[str, str] = {
    "europe": "اروپا",
    "north_america": "آمریکای شمالی",
    "asia": "آسیا و خاورمیانه",
    "oceania": "اقیانوسیه",
    "other": "سایر",
}

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

GREGORIAN_MONTH_FA = {
    1: "ژانویه",
    2: "فوریه",
    3: "مارس",
    4: "آوریل",
    5: "مه",
    6: "ژوئن",
    7: "ژوئیه",
    8: "اوت",
    9: "سپتامبر",
    10: "اکتبر",
    11: "نوامبر",
    12: "دسامبر",
}

# ---------------------------------------------------------------------------
# Text helpers (Persian normalization, markdown, digits)
# ---------------------------------------------------------------------------

_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_AR_DIACRITICS = re.compile("[\u064B-\u0652\u0670]")
_FA_DIGIT_MAP = str.maketrans(
    "0123456789۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "012345678901234567890123456789",
)


def linkify(text: str | None) -> Markup:
    """Convert ``[label](https://…)`` markdown links to safe <a> tags."""
    if not text:
        return Markup("")
    safe = str(escape(text))
    # escape() turns [...]() chars into themselves (no HTML chars inside except
    # & < >), so the markdown pattern still matches on the escaped string.
    replaced = _LINK_PATTERN.sub(
        r'<a href="\2" target="_blank" rel="noopener">\1</a>', safe
    )
    return Markup(replaced)


def strip_markdown(text: str | None) -> str:
    """Remove ``[label](url)`` markup for snippets / plain-text contexts."""
    if not text:
        return ""
    return _MD_LINK_PATTERN.sub(r"\1", text)


def fa_digits(value: Any) -> str:
    """Convert ASCII digits to Persian digits for display."""
    return str(value).translate(FA_DIGITS)


def format_updated(value: str | None) -> str:
    """Format an ISO ``YYYY-MM-DD`` date as Persian-readable Gregorian date.

    Example: ``"2026-09-18"`` -> ``"۱۸ سپتامبر ۲۰۲۶"``.
    Falls back to the raw value when unparseable.
    """
    if not value:
        return "—"
    text = str(value).strip()[:10]
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return fa_digits(text)
    month = GREGORIAN_MONTH_FA.get(dt.month, "")
    return f"{fa_digits(dt.day)} {month} {fa_digits(dt.year)}".strip()


def normalize_fa(text: str | None) -> str:
    """Normalize Persian text for search and comparison.

    - Arabic ي/ك/ى/ة variants -> Persian ی/ک/ی/ه
    - ZWNJ / half-space and other zero-width chars -> space
    - Diacritics (tashkeel) and tatweel removed
    - آ/أ/إ -> ا, ؤ -> و
    - Lowercased, digits unified to ASCII, whitespace collapsed
    """
    if not text:
        return ""
    t = str(text)
    # Zero-width / invisible chars -> space (so نیم‌فاصله == فاصله for search).
    t = (
        t.replace("\u200c", " ")
        .replace("\u200b", " ")
        .replace("\u200d", " ")
        .replace("\ufeff", " ")
        .replace("\u00a0", " ")
    )
    t = _AR_DIACRITICS.sub("", t)
    t = t.replace("\u0640", "")  # tatweel ـ
    t = t.replace("\u0643", "\u06a9")  # ك -> ک
    t = t.replace("\u064a", "\u06cc")  # ي -> ی
    t = t.replace("\u0649", "\u06cc")  # ى -> ی
    t = t.replace("ة", "ه")
    t = t.replace("ؤ", "و").replace("إ", "ا").replace("أ", "ا").replace("آ", "ا")
    t = t.lower()
    t = t.translate(_FA_DIGIT_MAP)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize_query(normalized_query: str) -> list[str]:
    """Split a normalized query into meaningful tokens."""
    tokens = [tok for tok in normalized_query.split(" ") if tok]
    # Drop single-char noise (e.g. و، به، در remnants) unless that's all we have.
    long_tokens = [tok for tok in tokens if len(tok) >= 2]
    return long_tokens or tokens


# ---------------------------------------------------------------------------
# In-memory data store (load once at startup, keep in RAM)
# ---------------------------------------------------------------------------

Guides = dict[str, dict[str, Any]]

_GUIDES: Guides | None = None
_GUIDES_MTIME: float = 0.0


def load_guides_from_disk() -> Guides:
    """Read and parse ``data/guides.json`` from disk (single place)."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("guides.json must contain a top-level object")
    return data


def get_guides(force_reload: bool = False) -> Guides:
    """Return cached guides; reload only when the file changed on disk.

    The JSON file is read once at startup and kept in memory. In development
    (editing the JSON by hand) a changed mtime triggers a transparent reload
    so you don't need to restart the server.
    """
    global _GUIDES, _GUIDES_MTIME
    try:
        mtime = DATA_PATH.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _GUIDES is None or force_reload or mtime != _GUIDES_MTIME:
        _GUIDES = load_guides_from_disk()
        _GUIDES_MTIME = mtime
    return _GUIDES


# Backwards-compat alias (old code called load_guides() per request).
def load_guides() -> Guides:
    return get_guides()


def get_country_meta(country: dict[str, Any]) -> dict[str, str]:
    """Country meta now lives inside guides.json under ``country["meta"]``."""
    meta = country.get("meta") or {}
    return {
        "capital": meta.get("capital", "") or "",
        "currency": meta.get("currency", "") or "",
        "language": meta.get("language", "") or "",
        "emergency": meta.get("emergency", "") or "",
        "region": meta.get("region", "other") or "other",
        "region_label": meta.get("region_label", "")
        or REGION_FALLBACK.get(meta.get("region", "other"), "سایر"),
    }


def get_regions(guides: Guides | None = None) -> dict[str, str]:
    """Collect ``{region_code: label}`` from data, in preferred order."""
    guides = guides if guides is not None else get_guides()
    found: dict[str, str] = {}
    for code, country in guides.items():
        if code == "general":
            continue
        meta = get_country_meta(country)
        found.setdefault(meta["region"], meta["region_label"])
    ordered: dict[str, str] = {}
    for key in REGION_ORDER:
        if key in found:
            ordered[key] = found[key] or REGION_FALLBACK.get(key, key)
    for key, label in found.items():
        if key not in ordered:
            ordered[key] = label or REGION_FALLBACK.get(key, key)
    return ordered or dict(REGION_FALLBACK)


def get_stats(guides: Guides | None = None) -> dict[str, int]:
    """Count countries / categories / items (general included in items)."""
    guides = guides if guides is not None else get_guides()
    countries = {k: v for k, v in guides.items() if k != "general"}
    n_countries = len(countries)
    n_categories = sum(len(c.get("categories", {})) for c in countries.values())
    n_items = sum(
        len(cat.get("items", []))
        for c in countries.values()
        for cat in c.get("categories", {}).values()
    )
    general_items = 0
    general = guides.get("general")
    if isinstance(general, dict):
        general_items = sum(
            len(cat.get("items", []))
            for cat in general.get("categories", {}).values()
        )
    return {
        "countries": n_countries,
        "categories": n_categories,
        "items": n_items + general_items,
    }


# ---------------------------------------------------------------------------
# Search index (built once, reused for every query)
# ---------------------------------------------------------------------------


class SearchDoc(TypedDict):
    country_code: str
    country_name: str
    flag: str
    category_code: str
    category_title: str
    item_title: str
    content: str
    norm_title: str
    norm_country: str
    norm_category: str
    norm_content: str
    nospace_title: str
    nospace_content: str
    last_updated: str


_SEARCH_INDEX: list[SearchDoc] | None = None
_SEARCH_INDEX_MTIME: float = 0.0

# Ranking weights: title > country name > category > content.
W_TITLE = 10.0
W_COUNTRY = 6.0
W_CATEGORY = 4.0
W_CONTENT = 2.0
W_NOSPACE_FACTOR = 0.7  # fallback when نيم‌فاصله/فاصله differ
PHRASE_TITLE = 15.0
PHRASE_COUNTRY = 8.0
PHRASE_CONTENT = 3.0
ALL_TOKENS_BONUS = 5.0


def build_search_index(guides: Guides | None = None) -> list[SearchDoc]:
    """Precompute normalized fields for every guide item (runs once)."""
    guides = guides if guides is not None else get_guides()
    docs: list[SearchDoc] = []
    for code, country in guides.items():
        cname = str(country.get("name", ""))
        flag = str(country.get("flag", ""))
        last_updated = str(country.get("last_updated", "") or "")
        norm_country = normalize_fa(cname)
        for cat_code, cat in country.get("categories", {}).items():
            cat_title = str(cat.get("title", ""))
            norm_category = normalize_fa(cat_title)
            for item in cat.get("items", []):
                title = str(item.get("title", ""))
                content = strip_markdown(str(item.get("content", "")))
                norm_title = normalize_fa(title)
                norm_content = normalize_fa(content)
                docs.append(
                    {
                        "country_code": code,
                        "country_name": cname,
                        "flag": flag,
                        "category_code": str(cat_code),
                        "category_title": cat_title,
                        "item_title": title,
                        "content": content,
                        "norm_title": norm_title,
                        "norm_country": norm_country,
                        "norm_category": norm_category,
                        "norm_content": norm_content,
                        "nospace_title": norm_title.replace(" ", ""),
                        "nospace_content": norm_content.replace(" ", ""),
                        "last_updated": last_updated,
                    }
                )
    return docs


def get_search_index() -> list[SearchDoc]:
    """Cached search index; rebuilt when guides.json changes."""
    global _SEARCH_INDEX, _SEARCH_INDEX_MTIME
    guides = get_guides()
    if _SEARCH_INDEX is None or _GUIDES_MTIME != _SEARCH_INDEX_MTIME:
        _SEARCH_INDEX = build_search_index(guides)
        _SEARCH_INDEX_MTIME = _GUIDES_MTIME
    return _SEARCH_INDEX


def make_snippet(content: str, norm_content: str, tokens: list[str], width: int = 150) -> str:
    """Extract a readable window around the first token hit.

    Works on the plain-text (de-markdowned) content; because normalization
    preserves length for the common cases, the normalized hit position maps
    closely onto the display string.
    """
    plain = (content or "").strip()
    if not plain:
        return ""
    if not tokens:
        snippet = plain[:width].strip()
        return snippet + ("…" if len(plain) > width else "")

    best = -1
    for tok in tokens:
        idx = norm_content.find(tok)
        if idx != -1 and (best == -1 or idx < best):
            best = idx
        nospace_tok = tok.replace(" ", "")
        if idx == -1 and nospace_tok and nospace_tok != tok:
            idx_ns = norm_content.replace(" ", "").find(nospace_tok)
            if idx_ns != -1:
                # Approximate position back in spaced string.
                approx = int(idx_ns * (len(norm_content) / max(1, len(norm_content.replace(" ", "")))))
                if best == -1 or approx < best:
                    best = approx

    if best == -1:
        snippet = plain[:width].strip()
        return snippet + ("…" if len(plain) > width else "")

    # Clamp the proportional index to the display string.
    best = max(0, min(best, max(0, len(plain) - 1)))
    start = max(0, best - 60)
    end = min(len(plain), start + width)
    if end - start < width:
        start = max(0, end - width)
    snippet = plain[start:end].strip()
    # Prefer word boundaries.
    if start > 0:
        space = snippet.find(" ")
        if 0 < space < 20:
            snippet = snippet[space + 1 :]
        snippet = "…" + snippet
    if end < len(plain):
        space = snippet.rfind(" ")
        if space > len(snippet) - 20 and space > 0:
            snippet = snippet[:space]
        snippet = snippet + "…"
    return re.sub(r"\s+", " ", snippet)


class SearchResult(TypedDict):
    country_code: str
    country_name: str
    flag: str
    category_code: str
    category_title: str
    item_title: str
    snippet: str
    matched_in: str
    last_updated: str


def search_guides(
    query: str | None, guides: Guides | None = None, limit: int = 30
) -> list[SearchResult]:
    """Ranked Persian full-text search.

    - Normalizes ی/ک, half-spaces and digits before comparing.
    - Multi-word queries: every token ideally matches somewhere (AND);
      when nothing matches all tokens we gracefully fall back to partial (OR).
    - Ranking: item title > country name > category title > content,
      plus exact-phrase and all-tokens bonuses.
    """
    q_norm = normalize_fa(query or "")
    if len(q_norm) < 2:
        return []
    tokens = tokenize_query(q_norm)
    if not tokens:
        return []

    docs = get_search_index() if guides is None else build_search_index(guides)

    scored: list[tuple[float, int, SearchDoc, str]] = []
    for doc in docs:
        score = 0.0
        matched_count = 0
        matched_in_title = False
        matched_in_text = False
        for tok in tokens:
            tok_ns = tok.replace(" ", "")
            hit = False
            if tok and tok in doc["norm_title"]:
                score += W_TITLE
                hit = True
                matched_in_title = True
            elif tok_ns and tok_ns in doc["nospace_title"]:
                score += W_TITLE * W_NOSPACE_FACTOR
                hit = True
                matched_in_title = True
            if tok and tok in doc["norm_country"]:
                score += W_COUNTRY
                hit = True
            if tok and tok in doc["norm_category"]:
                score += W_CATEGORY
                hit = True
            if tok and tok in doc["norm_content"]:
                score += W_CONTENT
                hit = True
                matched_in_text = True
            elif tok_ns and tok_ns in doc["nospace_content"]:
                score += W_CONTENT * W_NOSPACE_FACTOR
                hit = True
                matched_in_text = True
            if hit:
                matched_count += 1

        if matched_count == 0:
            continue

        # Exact-phrase bonuses (full normalized query as substring).
        if q_norm in doc["norm_title"]:
            score += PHRASE_TITLE
            matched_in_title = True
        elif q_norm in doc["norm_country"]:
            score += PHRASE_COUNTRY
        elif q_norm in doc["norm_content"]:
            score += PHRASE_CONTENT
            matched_in_text = True

        if matched_count == len(tokens):
            score += ALL_TOKENS_BONUS * len(tokens)

        matched_in = "title" if matched_in_title else ("text" if matched_in_text else "meta")
        scored.append((score, matched_count, doc, matched_in))

    if not scored:
        return []

    # Prefer items matching ALL tokens when such results exist.
    full_matches = [s for s in scored if s[1] == len(tokens)]
    pool = full_matches if full_matches else scored

    pool.sort(key=lambda s: (-s[0], s[2]["country_name"], s[2]["item_title"]))

    results: list[SearchResult] = []
    for score, _count, doc, matched_in in pool[: max(1, limit)]:
        results.append(
            {
                "country_code": doc["country_code"],
                "country_name": doc["country_name"],
                "flag": doc["flag"],
                "category_code": doc["category_code"],
                "category_title": doc["category_title"],
                "item_title": doc["item_title"],
                "snippet": make_snippet(doc["content"], doc["norm_content"], tokens),
                "matched_in": matched_in,
                "last_updated": doc["last_updated"],
            }
        )
    return results


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["APP_NAME"] = APP_NAME

app.jinja_env.filters["linkify"] = linkify
app.jinja_env.filters["fa_digits"] = fa_digits
app.jinja_env.filters["format_updated"] = format_updated


@app.context_processor
def inject_brand() -> dict[str, Any]:
    return {
        "site_name": APP_NAME,
        "site_tagline": APP_TAGLINE_FA,
        "site_description": APP_DESCRIPTION_FA,
    }


@app.after_request
def add_security_headers(response):  # type: ignore[no-untyped-def]
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health")
@app.route("/ping")
def health():  # type: ignore[no-untyped-def]
    return jsonify(status="ok", app=APP_NAME), 200


@app.route("/")
def index():  # type: ignore[no-untyped-def]
    guides = get_guides()
    general = guides.get("general")
    countries = {k: v for k, v in guides.items() if k != "general"}
    stats = get_stats(guides)
    regions = get_regions(guides)
    enriched: dict[str, dict[str, Any]] = {}
    for code, country in countries.items():
        n_items = sum(
            len(cat.get("items", []))
            for cat in country.get("categories", {}).values()
        )
        enriched[code] = {
            **country,
            "meta": get_country_meta(country),
            "n_items": n_items,
        }
    latest_updated = max(
        (c.get("last_updated") or "" for c in countries.values()), default=""
    )
    return render_template(
        "index.html",
        countries=enriched,
        general=general,
        stats=stats,
        regions=regions,
        latest_updated=latest_updated,
    )


@app.route("/country/<country_code>")
def country_page(country_code: str):  # type: ignore[no-untyped-def]
    guides = get_guides()
    country = guides.get(country_code)
    if not country:
        abort(404)
    meta = get_country_meta(country)
    n_items = sum(
        len(cat.get("items", [])) for cat in country.get("categories", {}).values()
    )
    region = meta.get("region")
    related: dict[str, dict[str, Any]] = {}
    if region:
        for code, candidate in guides.items():
            if code in ("general", country_code):
                continue
            if get_country_meta(candidate).get("region") == region:
                related[code] = candidate
                if len(related) >= 3:
                    break
    return render_template(
        "country.html",
        country=country,
        country_code=country_code,
        category_meta=CATEGORY_META,
        meta=meta,
        n_items=n_items,
        related=related,
    )


@app.route("/country/<country_code>/<category>")
def category_page(country_code: str, category: str):  # type: ignore[no-untyped-def]
    guides = get_guides()
    country = guides.get(country_code)
    if not country:
        abort(404)
    cat_data = country.get("categories", {}).get(category)
    if not cat_data:
        abort(404)
    meta = get_country_meta(country)
    cat_meta = CATEGORY_META.get(
        category, {"icon": "book", "label": cat_data.get("title", "")}
    )
    return render_template(
        "guide.html",
        country=country,
        country_code=country_code,
        category=cat_data,
        category_code=category,
        cat_meta=cat_meta,
        meta=meta,
    )


@app.route("/search")
def search_page():  # type: ignore[no-untyped-def]
    q = (request.args.get("q", "") or "").strip()
    results = search_guides(q) if q else []
    guides = get_guides()
    total = len([k for k in guides if k != "general"])
    return render_template("search.html", q=q, results=results, total=total)


@app.route("/api/search")
def api_search():  # type: ignore[no-untyped-def]
    q = (request.args.get("q", "") or "").strip()
    try:
        limit = int(request.args.get("limit", "30"))
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, min(limit, 50))
    return jsonify(query=q, results=search_guides(q, limit=limit) if q else [])


@app.route("/api/countries")
def api_countries():  # type: ignore[no-untyped-def]
    guides = get_guides()
    out = []
    for code, country in guides.items():
        if code == "general":
            continue
        meta = get_country_meta(country)
        out.append(
            {
                "code": code,
                "name": country.get("name"),
                "flag": country.get("flag"),
                "region": meta.get("region", ""),
                "region_label": meta.get("region_label", ""),
                "capital": meta.get("capital", ""),
                "emergency": meta.get("emergency", ""),
                "last_updated": country.get("last_updated", ""),
                "items": sum(
                    len(cat.get("items", []))
                    for cat in country.get("categories", {}).values()
                ),
            }
        )
    return jsonify(out)


@app.route("/checklist")
def checklist():  # type: ignore[no-untyped-def]
    guides = get_guides()
    general = guides.get("general", {}) or {}
    arrival = general.get("categories", {}).get("arrival", {"items": []})
    return render_template("checklist.html", arrival=arrival)


@app.route("/emergency")
def emergency():  # type: ignore[no-untyped-def]
    guides = get_guides()
    rows = []
    for code, country in guides.items():
        if code == "general":
            continue
        meta = get_country_meta(country)
        rows.append(
            {
                "code": code,
                "name": country.get("name"),
                "flag": country.get("flag"),
                "capital": meta.get("capital", "") or "—",
                "emergency": meta.get("emergency", "") or "—",
                "currency": meta.get("currency", "") or "—",
                "language": meta.get("language", "") or "—",
                "region": meta.get("region_label", "") or "—",
                "last_updated": country.get("last_updated", ""),
            }
        )
    rows.sort(key=lambda r: str(r["name"]))
    return render_template("emergency.html", rows=rows)


@app.errorhandler(404)
def not_found(error):  # type: ignore[no-untyped-def]
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):  # type: ignore[no-untyped-def]
    log.exception("Unhandled error: %s", error)
    return render_template("500.html"), 500


# --- Keep-alive for Render free tier ---------------------------------------
def _keep_alive_loop() -> None:
    base_url = os.environ.get("KEEP_ALIVE_URL") or os.environ.get(
        "RENDER_EXTERNAL_URL"
    )
    if not base_url:
        return
    base_url = base_url.rstrip("/")
    try:
        interval = int(os.environ.get("KEEP_ALIVE_INTERVAL", "600"))
    except ValueError:
        interval = 600
    time.sleep(30)
    while True:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=10) as r:
                print(f"[keep-alive] ping {base_url}/health -> {r.status}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[keep-alive] ping failed: {e}", flush=True)
        time.sleep(interval)


if os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL"):
    threading.Thread(target=_keep_alive_loop, daemon=True).start()


# Warm the cache at import so the first real request is fast.
try:
    get_guides()
    get_search_index()
except Exception:  # noqa: BLE001
    log.exception("Failed to warm guides cache at startup")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
