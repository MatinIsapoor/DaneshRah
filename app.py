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
import secrets
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict
from xml.sax.saxutils import escape as xml_escape

from flask import Flask, Response, abort, g, jsonify, render_template, request, url_for
from markupsafe import Markup, escape
from werkzeug.middleware.proxy_fix import ProxyFix

from guide_validation import is_safe_url, validate_guides

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Branding / constants
# ---------------------------------------------------------------------------

APP_NAME = "DaneshRah"
APP_NAME_FA = "دانش‌راه"
APP_TAGLINE_FA = "راهنمای مستقل زندگی دانشجویی در خارج از کشور"
APP_DESCRIPTION_FA = (
    "دانش‌راه (DaneshRah): راهنمای فارسی و کاربردی زندگی دانشجویی در خارج از کشور — "
    "خرید، مسکن، امور اداری، کار دانشجویی و چک‌لیست روزهای اول، کشور به کشور."
)

#: Public origin used in canonical URLs, Open Graph tags, the sitemap and the
#: robots file. It deliberately does not come from the request Host header,
#: which a client can spoof. ``PUBLIC_BASE_URL`` can override it on any host.
_DEFAULT_SITE_URL = "https://daneshrah.onrender.com"


def _site_url_from_env() -> str:
    candidate = (
        os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("RENDER_EXTERNAL_URL")
        or _DEFAULT_SITE_URL
    ).strip().rstrip("/")
    if not re.match(r"^https?://[A-Za-z0-9.-]+(?::\d+)?$", candidate):
        return _DEFAULT_SITE_URL
    return candidate


SITE_URL = _site_url_from_env()

DATA_PATH = Path(__file__).parent / "data" / "guides.json"

#: Longest search query accepted (characters). Longer input is truncated.
MAX_QUERY_LENGTH = 200

#: Bounds for the ``limit`` parameter of the search API.
DEFAULT_SEARCH_LIMIT = 30
MAX_SEARCH_LIMIT = 50

#: Maximum accepted request body (the app has no POST endpoints, but a
#: runaway request must not be able to buffer arbitrary data).
MAX_CONTENT_LENGTH = 1 * 1024 * 1024

CATEGORY_META: dict[str, dict[str, str]] = {
    "shopping": {
        "icon": "cart",
        "label": "خرید و زندگی روزمره",
        "desc": "سوپرمارکت، سیم‌کارت، بانک، حمل‌ونقل و وسایل اولیه",
    },
    "housing": {
        "icon": "home",
        "label": "مسکن و اجاره‌خانه",
        "desc": "خوابگاه، اجاره، ودیعه، قرارداد و ثبت آدرس",
    },
    "admin": {
        "icon": "doc",
        "label": "اقامت، بیمه و امور اداری",
        "desc": "اقامت، بیمه‌ی سلامت، مالیات و شماره‌های شناسایی",
    },
    "work": {
        "icon": "brief",
        "label": "کار دانشجویی",
        "desc": "سقف ساعت مجاز، حداقل دستمزد، مالیات و کاریابی",
    },
    "arrival": {
        "icon": "compass",
        "label": "قدم‌های اول",
        "desc": "از فرودگاه تا استقرار کامل در روزهای اول",
    },
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


def safe_url(value: Any) -> str:
    """Return ``value`` when it is a safe absolute ``http(s)`` URL.

    Used for every URL that comes from ``data/guides.json`` so that a
    ``javascript:`` or ``data:`` payload can never reach an ``href``.
    Unsafe or malformed values render as an empty string.
    """
    if not isinstance(value, str):
        return ""
    url = value.strip()
    if not url or not is_safe_url(url):
        return ""
    return url


def clean_query(raw: Any) -> str:
    """Normalize a raw user query: strip control chars, collapse spaces, cap length."""
    if raw is None:
        return ""
    text = str(raw)
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_QUERY_LENGTH]


def fa_digits(value: Any) -> str:
    """Convert ASCII digits to Persian digits for display."""
    return str(value).translate(FA_DIGITS)


def latin_digits(value: Any) -> str:
    """Convert Persian/Arabic-Indic digits to ASCII.

    Used for machine-readable values such as ``tel:`` links and form values.
    """
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return str(value).translate(table)


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
_GUIDES_LOCK = threading.RLock()


def load_guides_from_disk() -> Guides:
    """Read and parse ``data/guides.json`` from disk (single place).

    The file is also validated structurally; problems are logged (they never
    break the running app, but they show up in the logs and in
    ``python guide_validation.py``).
    """
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("guides.json must contain a top-level object")

    issues = validate_guides(data)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    if errors:
        log.error(
            "guides.json: %d validation error(s); first: %s", len(errors), errors[0]
        )
    if warnings:
        log.warning(
            "guides.json: %d validation warning(s); first: %s", len(warnings), warnings[0]
        )
    return data


def get_guides(force_reload: bool = False) -> Guides:
    """Return cached guides; reload only when the file changed on disk.

    The JSON file is read once at startup and kept in memory. In development
    (editing the JSON by hand) a changed mtime triggers a transparent reload
    so you don't need to restart the server.
    """
    global _GUIDES, _GUIDES_MTIME
    with _GUIDES_LOCK:
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
        "sources": sum(
            len(c.get("sources", []) or []) for c in countries.values()
        ),
    }


def get_latest_updated(guides: Guides | None = None) -> str:
    """Return the newest ``last_updated`` value in the data file.

    This is a *file-level* freshness stamp, not proof that every country was
    individually re-checked. The UI labels it accordingly.
    """
    guides = guides if guides is not None else get_guides()
    dates = [
        str(v.get("last_updated", "") or "")
        for v in guides.values()
        if isinstance(v, dict)
    ]
    return max(dates, default="")


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
    anchor: str
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
            for item_index, item in enumerate(cat.get("items", []), start=1):
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
                        "anchor": f"item-{item_index}",
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
    with _GUIDES_LOCK:
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
    anchor: str


def search_guides_with_total(
    query: str | None,
    guides: Guides | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> tuple[list[SearchResult], int]:
    """Ranked Persian full-text search, returning ``(page, total_matches)``.

    - Normalizes ی/ک, half-spaces and digits before comparing.
    - Multi-word queries: every token ideally matches somewhere (AND);
      when nothing matches all tokens we gracefully fall back to partial (OR).
    - Ranking: item title > country name > category title > content,
      plus exact-phrase and all-tokens bonuses.
    """
    q_norm = normalize_fa(query or "")
    if len(q_norm) < 2:
        return [], 0
    tokens = tokenize_query(q_norm)
    if not tokens:
        return [], 0
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_SEARCH_LIMIT
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))

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
        return [], 0

    # Prefer items matching ALL tokens when such results exist.
    full_matches = [s for s in scored if s[1] == len(tokens)]
    pool = full_matches if full_matches else scored

    pool.sort(key=lambda s: (-s[0], s[2]["country_name"], s[2]["item_title"]))
    total = len(pool)

    results: list[SearchResult] = []
    for score, _count, doc, matched_in in pool[:limit]:
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
                "anchor": doc["anchor"],
            }
        )
    return results, total


def search_guides(
    query: str | None, guides: Guides | None = None, limit: int = DEFAULT_SEARCH_LIMIT
) -> list[SearchResult]:
    """Backwards-compatible wrapper around :func:`search_guides_with_total`."""
    results, _total = search_guides_with_total(query, guides=guides, limit=limit)
    return results


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["APP_NAME"] = APP_NAME
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
# The app does not use Flask sessions, but setting safe cookie defaults costs
# nothing and prevents a future session from becoming insecure by accident.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG", "0") != "1",
)
# Keep Persian characters readable in the JSON API responses.
app.json.ensure_ascii = False
app.json.sort_keys = False

# Render (and any other reverse proxy) terminates TLS and forwards the
# original scheme in ``X-Forwarded-Proto``; without ProxyFix Flask would
# believe every request is plain HTTP. The host header is deliberately *not*
# trusted (no ``x_host``) so that a spoofed Host cannot change generated URLs.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)


def canonical_url(path: str | None = None) -> str:
    """Absolute canonical URL for the current (or given) same-site path.

    ``SITE_URL`` is configuration, never the request Host header, so a spoofed
    ``Host`` cannot inject an attacker-controlled canonical link.
    """
    target = path if path is not None else (request.path if request else "/")
    if not target.startswith("/"):
        target = "/" + target
    return f"{SITE_URL}{target}"


def _safe_site_last_updated() -> str:
    try:
        return get_latest_updated()
    except Exception:  # noqa: BLE001 - the error page must still render
        log.exception("Could not determine the data-file update date")
        return ""


def _safe_site_stats() -> dict[str, int]:
    try:
        return get_stats()
    except Exception:  # noqa: BLE001 - the error page must still render
        log.exception("Could not determine site statistics")
        return {"countries": 0, "categories": 0, "items": 0, "sources": 0}

def flag_code(flag: str | None) -> str:
    """Convert a flag emoji into an ISO-3166 alpha-2 code.

    ``"🇩🇪"`` -> ``"de"``. Returns an empty string when the flag is not made
    of regional-indicator symbols.
    """
    if not flag:
        return ""
    letters = []
    for ch in str(flag):
        cp = ord(ch)
        if 0x1F1E6 <= cp <= 0x1F1FF:
            letters.append(chr(cp - 0x1F1E6 + ord("A")))
    return "".join(letters).lower()


def flag_url(flag: str | None, size: int = 80) -> str:
    """Return a crisp flag image URL for a flag emoji (empty when unknown)."""
    code = flag_code(flag)
    if not code:
        return ""
    return f"https://flagcdn.com/w{size}/{code}.png"


app.jinja_env.filters["linkify"] = linkify
app.jinja_env.filters["fa_digits"] = fa_digits
app.jinja_env.filters["latin_digits"] = latin_digits
app.jinja_env.filters["format_updated"] = format_updated
app.jinja_env.filters["flag_code"] = flag_code
app.jinja_env.filters["flag_url"] = flag_url
app.jinja_env.filters["safe_url"] = safe_url


@app.context_processor
def inject_brand() -> dict[str, Any]:
    nonce = getattr(g, "csp_nonce", "")
    if not nonce:
        nonce = secrets.token_urlsafe(16)
        g.csp_nonce = nonce
    stats = _safe_site_stats()
    return {
        "site_name": APP_NAME,
        "site_name_fa": APP_NAME_FA,
        "site_tagline": APP_TAGLINE_FA,
        "site_description": APP_DESCRIPTION_FA,
        "site_url": SITE_URL,
        "canonical_url": canonical_url(request.path),
        "site_stats": stats,
        "site_last_updated": _safe_site_last_updated(),
        "current_year_fa": fa_digits(datetime.now().year),
        "csp_nonce": nonce,
    }


def _content_security_policy(nonce: str) -> str:
    """Build the CSP header.

    Scripts are restricted to same-origin files plus the single inline
    bootstrap script, which carries the per-request nonce. All styles now live
    in the stylesheet, so ``unsafe-inline`` is not needed for styles.
    """
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "frame-src 'none'",
            "form-action 'self'",
            "img-src 'self' data: https://flagcdn.com",
            "style-src 'self' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            f"script-src 'self' 'nonce-{nonce}'",
            "connect-src 'self'",
            "manifest-src 'self'",
            "worker-src 'none'",
            "media-src 'none'",
        ]
    )


@app.before_request
def assign_request_context() -> None:
    """Give every request its own CSP nonce and a lightweight request id."""
    g.csp_nonce = secrets.token_urlsafe(16)
    incoming = (request.headers.get("X-Request-ID") or "").strip()
    if not re.match(r"^[A-Za-z0-9._-]{8,64}$", incoming):
        incoming = secrets.token_hex(8)
    g.request_id = incoming


@app.after_request
def add_security_headers(response):  # type: ignore[no-untyped-def]
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), geolocation=(), microphone=(), payment=(), usb=(), "
        "magnetometer=(), gyroscope=(), accelerometer=()",
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault(
        "X-Request-ID", getattr(g, "request_id", secrets.token_hex(8))
    )
    nonce = getattr(g, "csp_nonce", None) or secrets.token_urlsafe(16)
    response.headers.setdefault(
        "Content-Security-Policy", _content_security_policy(nonce)
    )
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    path = request.path
    if path in ("/health", "/ping"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/api/search"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path in ("/api/countries", "/sitemap.xml", "/robots.txt"):
        response.headers.setdefault("Cache-Control", "public, max-age=300")
    if path in ("/health", "/ping") or path.startswith("/api/"):
        response.headers.setdefault("X-Robots-Tag", "noindex")
    elif path == "/search" or path.startswith("/country/general"):
        # Search result pages and the generic checklist text are duplicates
        # that should not compete with the canonical country guides in search.
        response.headers.setdefault("X-Robots-Tag", "noindex, follow")
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health")
@app.route("/ping")
def health():  # type: ignore[no-untyped-def]
    """Liveness + data-load check used by Render."""
    try:
        guides = get_guides()
        stats = get_stats(guides)
    except Exception:  # noqa: BLE001 - a broken data file should be visible
        log.exception("Health check failed: guides data could not be loaded")
        return jsonify(status="degraded", app=APP_NAME), 503
    return (
        jsonify(
            status="ok",
            app=APP_NAME,
            countries=stats["countries"],
            guides=stats["items"],
        ),
        200,
    )


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
    latest_updated = get_latest_updated(guides)
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
                related[code] = {**candidate, "meta": get_country_meta(candidate)}
                if len(related) >= 3:
                    break
    categories = country.get("categories", {}) or {}
    ordered_codes = [
        code for code in ("shopping", "housing", "admin", "work") if code in categories
    ] + [code for code in categories if code not in ("shopping", "housing", "admin", "work")]
    category_cards = []
    for code in ordered_codes:
        category = categories.get(code, {}) or {}
        info = CATEGORY_META.get(code, {})
        category_cards.append(
            {
                "code": code,
                "title": category.get("title") or info.get("label") or code,
                "label": info.get("label") or category.get("title") or code,
                "desc": info.get("desc") or "",
                "icon": info.get("icon") or "book",
                "items": len(category.get("items", []) or []),
                "sources": len(
                    [
                        source
                        for source in (country.get("sources", []) or [])
                        if isinstance(source, dict) and source.get("cat") == code
                    ]
                ),
            }
        )
    return render_template(
        "country.html",
        country=country,
        country_code=country_code,
        category_meta=CATEGORY_META,
        category_cards=category_cards,
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
        category, {"icon": "book", "label": cat_data.get("title", ""), "desc": ""}
    )
    sources = country.get("sources", []) or []
    category_sources = [
        source
        for source in sources
        if isinstance(source, dict) and source.get("cat") == category
    ]
    reading_words = 0
    for item in cat_data.get("items", []) or []:
        reading_words += len(str(item.get("title", "")).split())
        reading_words += len(str(item.get("content", "")).split())
    read_minutes = max(1, round(reading_words / 180)) if reading_words else 1
    return render_template(
        "guide.html",
        country=country,
        country_code=country_code,
        category=cat_data,
        category_code=category,
        cat_meta=cat_meta,
        meta=meta,
        category_sources=category_sources,
        read_minutes=read_minutes,
    )


@app.route("/search")
def search_page():  # type: ignore[no-untyped-def]
    raw = request.args.get("q", "") or ""
    q = clean_query(raw)
    results, total_matches = (
        search_guides_with_total(q) if q else ([], 0)
    )
    guides = get_guides()
    total = len([k for k in guides if k != "general"])
    return render_template(
        "search.html",
        q=q,
        results=results,
        total=total,
        total_matches=total_matches,
        truncated=len(raw.strip()) > MAX_QUERY_LENGTH,
        max_query_length=MAX_QUERY_LENGTH,
    )


@app.route("/api/search")
def api_search():  # type: ignore[no-untyped-def]
    raw = request.args.get("q", "") or ""
    q = clean_query(raw)
    try:
        limit = int(request.args.get("limit", str(DEFAULT_SEARCH_LIMIT)))
    except (TypeError, ValueError):
        limit = DEFAULT_SEARCH_LIMIT
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    results, total_matches = (
        search_guides_with_total(q, limit=limit) if q else ([], 0)
    )
    return jsonify(
        query=q,
        truncated=len(raw.strip()) > MAX_QUERY_LENGTH,
        limit=limit,
        total=total_matches,
        results=results,
    )


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


@app.route("/about")
def about():  # type: ignore[no-untyped-def]
    guides = get_guides()
    return render_template(
        "about.html",
        stats=get_stats(guides),
        latest_updated=get_latest_updated(guides),
    )


@app.route("/robots.txt")
def robots_txt():  # type: ignore[no-untyped-def]
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /health",
        "Disallow: /ping",
        "Disallow: /search",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():  # type: ignore[no-untyped-def]
    guides = get_guides()
    file_updated = get_latest_updated(guides)
    entries: list[tuple[str, str]] = [
        ("/", file_updated),
        ("/checklist", file_updated),
        ("/emergency", file_updated),
        ("/about", file_updated),
    ]
    for code, country in guides.items():
        if code == "general":
            continue
        updated = str(country.get("last_updated", "") or file_updated)
        entries.append((f"/country/{code}", updated))
        for category in country.get("categories", {}):
            entries.append((f"/country/{code}/{category}", updated))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in entries:
        loc = xml_escape(f"{SITE_URL}{path}")
        parts.append("<url>")
        parts.append(f"<loc>{loc}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{xml_escape(lastmod)}</lastmod>")
        parts.append("</url>")
    parts.append("</urlset>")
    return Response("\n".join(parts), mimetype="application/xml")


def _render_error(code: int, title: str, message: str):  # type: ignore[no-untyped-def]
    response = app.make_response(
        render_template(
            "error.html",
            error_code=code,
            error_code_fa=fa_digits(code),
            error_title=title,
            error_message=message,
        )
    )
    response.status_code = code
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@app.errorhandler(400)
def bad_request(error):  # type: ignore[no-untyped-def]
    return _render_error(
        400,
        "درخواست معتبر نیست",
        "نشانی درخواست کامل یا معتبر نبود. به صفحه‌ی اصلی برگرد و دوباره امتحان کن.",
    )


@app.errorhandler(404)
def not_found(error):  # type: ignore[no-untyped-def]
    return _render_error(
        404,
        "این صفحه پیدا نشد",
        "یا نشانی را اشتباه زده‌ای، یا صفحه جابه‌جا شده است. از همین‌جا می‌توانی راه را پیدا کنی.",
    )


@app.errorhandler(405)
def method_not_allowed(error):  # type: ignore[no-untyped-def]
    return _render_error(
        405,
        "این روش پشتیبانی نمی‌شود",
        "این نشانی فقط برای خواندن صفحه است. از دکمه‌ها و فرم‌های خود سایت استفاده کن.",
    )


@app.errorhandler(413)
def request_too_large(error):  # type: ignore[no-untyped-def]
    return _render_error(
        413,
        "درخواست بیش از حد بزرگ است",
        "حجم درخواست از محدودیت مجاز بیشتر بود. محتوای کمتری بفرست و دوباره امتحان کن.",
    )


@app.errorhandler(500)
def internal_error(error):  # type: ignore[no-untyped-def]
    log.error(
        "Unhandled error while serving request %s",
        getattr(g, "request_id", "-"),
        exc_info=True,
    )
    return _render_error(
        500,
        "یک خطای غیرمنتظره رخ داد",
        "خطا ثبت شد. یک‌بار صفحه را تازه کن؛ اگر درست نشد، کمی بعد دوباره سر بزن.",
    )


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
