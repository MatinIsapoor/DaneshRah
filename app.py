"""
راهنمای دانشجویان ایرانی خارج از کشور
Flask app: country guides, search, checklist, emergency numbers.
"""

import json
import os
import re
import threading
import time
import urllib.request
from pathlib import Path
from flask import Flask, jsonify, render_template, abort, request
from markupsafe import Markup

app = Flask(__name__)

DATA_PATH = Path(__file__).parent / "data" / "guides.json"

_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def linkify(text):
    """تبدیل لینک‌های مارک‌داون [متن](آدرس) به <a> با باز شدن در تب جدید"""
    if not text:
        return text
    replaced = _LINK_PATTERN.sub(
        r'<a href="\2" target="_blank" rel="noopener">\1</a>', text
    )
    return Markup(replaced)


app.jinja_env.filters["linkify"] = linkify


# ---------------------------------------------------------------- meta

CATEGORY_META = {
    "shopping": {"icon": "cart", "label": "خرید و زندگی روزمره"},
    "housing": {"icon": "home", "label": "مسکن و اجاره‌خانه"},
    "arrival": {"icon": "compass", "label": "قدم‌های اول"},
}

# enriching data without touching guides.json
COUNTRY_META = {
    "germany": {"capital": "برلین", "currency": "یورو (€)", "language": "آلمانی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "uk": {"capital": "لندن", "currency": "پوند (£)", "language": "انگلیسی", "emergency": "۹۹۹", "region": "europe", "region_label": "اروپا"},
    "france": {"capital": "پاریس", "currency": "یورو (€)", "language": "فرانسوی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "italy": {"capital": "رم", "currency": "یورو (€)", "language": "ایتالیایی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "spain": {"capital": "مادرید", "currency": "یورو (€)", "language": "اسپانیایی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "netherlands": {"capital": "آمستردام", "currency": "یورو (€)", "language": "هلندی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "austria": {"capital": "وین", "currency": "یورو (€)", "language": "آلمانی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "sweden": {"capital": "استکهلم", "currency": "کرون (kr)", "language": "سوئدی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "canada": {"capital": "اتاوا", "currency": "دلار کانادا", "language": "انگلیسی / فرانسوی", "emergency": "۹۱۱", "region": "north_america", "region_label": "آمریکای شمالی"},
    "usa": {"capital": "واشنگتن", "currency": "دلار آمریکا", "language": "انگلیسی", "emergency": "۹۱۱", "region": "north_america", "region_label": "آمریکای شمالی"},
    "turkey": {"capital": "آنکارا", "currency": "لیر (₺)", "language": "ترکی", "emergency": "۱۱۲", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "uae": {"capital": "ابوظبی", "currency": "درهم", "language": "عربی", "emergency": "۹۹۹", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "malaysia": {"capital": "کوالالامپور", "currency": "رینگیت (RM)", "language": "مالایی", "emergency": "۹۹۹", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "china": {"capital": "پکن", "currency": "یوآن (¥)", "language": "چینی", "emergency": "۱۱۰", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "russia": {"capital": "مسکو", "currency": "روبل (₽)", "language": "روسی", "emergency": "۱۱۲", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "armenia": {"capital": "ایروان", "currency": "درام (֏)", "language": "ارمنی", "emergency": "۹۱۱", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "australia": {"capital": "کانبرا", "currency": "دلار استرالیا", "language": "انگلیسی", "emergency": "۰۰۰", "region": "oceania", "region_label": "اقیانوسیه"},
    "hungary": {"capital": "بوداپست", "currency": "فورینت (Ft)", "language": "مجاری", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "poland": {"capital": "ورشو", "currency": "زلوتی (zł)", "language": "لهستانی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "finland": {"capital": "هلسینکی", "currency": "یورو (€)", "language": "فنلاندی / سوئدی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "ireland": {"capital": "دوبلین", "currency": "یورو (€)", "language": "انگلیسی", "emergency": "۱۱۲", "region": "europe", "region_label": "اروپا"},
    "cyprus": {"capital": "نیکوزیا", "currency": "یورو (€)", "language": "یونانی / ترکی / انگلیسی", "emergency": "۱۱۲", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "georgia": {"capital": "تفلیس", "currency": "لاری (₾)", "language": "گرجی", "emergency": "۱۱۲", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "south_korea": {"capital": "سئول", "currency": "وون (₩)", "language": "کره‌ای", "emergency": "۱۱۲", "region": "asia", "region_label": "آسیا و خاورمیانه"},
    "japan": {"capital": "توکیو", "currency": "ین (¥)", "language": "ژاپنی", "emergency": "۱۱۰", "region": "asia", "region_label": "آسیا و خاورمیانه"},
}

REGIONS = {
    "europe": "اروپا",
    "north_america": "آمریکای شمالی",
    "asia": "آسیا و خاورمیانه",
    "oceania": "اقیانوسیه",
}


def load_guides():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_stats(guides=None):
    guides = guides or load_guides()
    countries = {k: v for k, v in guides.items() if k != "general"}
    n_countries = len(countries)
    n_categories = sum(len(c.get("categories", {})) for c in countries.values())
    n_items = sum(
        len(cat.get("items", []))
        for c in countries.values()
        for cat in c.get("categories", {}).values()
    )
    general_items = 0
    if "general" in guides:
        general_items = sum(
            len(cat.get("items", []))
            for cat in guides["general"].get("categories", {}).values()
        )
    return {
        "countries": n_countries,
        "categories": n_categories,
        "items": n_items + general_items,
    }


def search_guides(query, guides=None, limit=30):
    guides = guides or load_guides()
    q = (query or "").strip()
    if len(q) < 2:
        return []
    results = []
    for code, country in guides.items():
        cname = country.get("name", "")
        for cat_code, cat in country.get("categories", {}).items():
            cat_title = cat.get("title", "")
            for item in cat.get("items", []):
                title = item.get("title", "")
                content = item.get("content", "")
                hay = f"{cname} {cat_title} {title} {content}"
                if q in hay:
                    idx = hay.find(q)
                    start = max(0, idx - 60)
                    snippet = hay[start:start + 140].strip()
                    results.append({
                        "country_code": code,
                        "country_name": cname,
                        "flag": country.get("flag", ""),
                        "category_code": cat_code,
                        "category_title": cat_title,
                        "item_title": title,
                        "snippet": snippet,
                    })
                    if len(results) >= limit:
                        return results
    return results


# ---------------------------------------------------------------- routes

@app.route("/health")
@app.route("/ping")
def health():
    return jsonify(status="ok"), 200


@app.route("/")
def index():
    guides = load_guides()
    general = guides.pop("general", None)
    stats = get_stats({**guides, **({"general": general} if general else {})})
    # attach meta + counts for template
    enriched = {}
    for code, c in guides.items():
        meta = COUNTRY_META.get(code, {})
        n_items = sum(len(cat.get("items", [])) for cat in c.get("categories", {}).values())
        enriched[code] = {**c, "meta": meta, "n_items": n_items}
    return render_template("index.html", countries=enriched, general=general,
                           stats=stats, regions=REGIONS)


@app.route("/country/<country_code>")
def country_page(country_code):
    guides = load_guides()
    country = guides.get(country_code)
    if not country:
        abort(404)
    meta = COUNTRY_META.get(country_code, {})
    n_items = sum(len(cat.get("items", [])) for cat in country.get("categories", {}).values())
    # related: same region
    region = meta.get("region")
    related = {}
    if region:
        for code, c in guides.items():
            if code in ("general", country_code):
                continue
            if COUNTRY_META.get(code, {}).get("region") == region:
                related[code] = c
                if len(related) >= 3:
                    break
    return render_template("country.html", country=country, country_code=country_code,
                           category_meta=CATEGORY_META, meta=meta,
                           n_items=n_items, related=related)


@app.route("/country/<country_code>/<category>")
def category_page(country_code, category):
    guides = load_guides()
    country = guides.get(country_code)
    if not country:
        abort(404)
    cat_data = country.get("categories", {}).get(category)
    if not cat_data:
        abort(404)
    meta = COUNTRY_META.get(country_code, {})
    cat_meta = CATEGORY_META.get(category, {"icon": "book", "label": cat_data.get("title", "")})
    return render_template("guide.html", country=country, country_code=country_code,
                           category=cat_data, category_code=category,
                           cat_meta=cat_meta, meta=meta)


@app.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    guides = load_guides()
    results = search_guides(q, guides) if q else []
    total = len([k for k in guides if k != "general"])
    return render_template("search.html", q=q, results=results, total=total)


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    return jsonify(query=q, results=search_guides(q) if q else [])


@app.route("/api/countries")
def api_countries():
    guides = load_guides()
    guides.pop("general", None)
    out = []
    for code, c in guides.items():
        out.append({
            "code": code,
            "name": c.get("name"),
            "flag": c.get("flag"),
            "region": COUNTRY_META.get(code, {}).get("region", ""),
            "items": sum(len(cat.get("items", [])) for cat in c.get("categories", {}).values()),
        })
    return jsonify(out)


@app.route("/checklist")
def checklist():
    guides = load_guides()
    general = guides.get("general", {})
    arrival = general.get("categories", {}).get("arrival", {"items": []})
    return render_template("checklist.html", arrival=arrival)


@app.route("/emergency")
def emergency():
    guides = load_guides()
    rows = []
    for code, c in guides.items():
        if code == "general":
            continue
        meta = COUNTRY_META.get(code, {})
        rows.append({
            "code": code,
            "name": c.get("name"),
            "flag": c.get("flag"),
            "capital": meta.get("capital", "—"),
            "emergency": meta.get("emergency", "—"),
            "currency": meta.get("currency", "—"),
            "language": meta.get("language", "—"),
            "region": meta.get("region_label", "—"),
        })
    rows.sort(key=lambda r: r["name"])
    return render_template("emergency.html", rows=rows)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# --- Keep-alive for Render free tier ---
def _keep_alive_loop():
    base_url = os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
