# 🎓 DaneshRah | دانش‌راه

**DaneshRah** helps Iranian students with the small-but-critical questions nobody tells you before moving abroad — country-by-country guides for shopping, housing, admin, student jobs, plus an interactive arrival checklist.

🌐 **Live Demo:** [daneshrah.onrender.com](https://daneshrah.onrender.com)

> من متینم؛ دانشجوی ایرانی در پاریس. دانش‌راه را ساختم تا جواب همان سؤال‌های ریزِ هفته‌های اولِ مهاجرت — از ودیعه و سیم‌کارت تا بیمه و اقامت — یک‌جا و همراه با لینک منبع رسمی در دسترس باشد. اطلاعات هر کشور در یک فایل JSON نگهداری می‌شود و هر صفحه تاریخ آخرین بازبینی دارد. اگر جایی اشتباه یا قدیمی بود، از طریق GitHub بگو تا اصلاح شود.

## ✨ Features

* 🌍 **42 country guides** — Germany, Canada, USA, Turkey, UK, Italy, Netherlands, Australia, Malaysia, France, Austria, China, Russia, UAE, Spain, Sweden, Armenia, Hungary, Poland, Cyprus, Georgia, South Korea, Japan, Finland, Ireland, Norway, Denmark, Belgium, Switzerland, Portugal, Czechia, Azerbaijan, Qatar, Kuwait, Oman, Uzbekistan, India, Singapore, New Zealand, Saudi Arabia, Jordan, Egypt
* 🔎 **Smart Persian search** — normalization (ی/ک عربی، نیم‌فاصله، اعداد فارسی), multi-word queries, ranked results (title > country name > category > content), clean snippets (`/search` + live API `/api/search?limit=30`)
* 🕓 **`last_updated` per country** — every guide shows «به‌روز شده: …» so you know how fresh it is
* 🧭 **First-days arrival checklist** — interactive, saved in your browser (`/checklist`, with progressbar + ARIA)
* 🚨 **Emergency & essentials table** — capitals, currencies, languages, emergency numbers, region, last check (`/emergency`)
* 📚 4 categorized guides per country (shopping / housing / admin & residence / student jobs) with links to official sources
* 🌙 **Dark mode**, SVG animations, reading progress bar, table of contents, print-friendly guides
* ⭐ **Favorites** — bookmark countries (localStorage, key `daneshrah-favs`), region filters, animated stats
* 📱 Fully responsive RTL Persian interface (Vazirmatn font)
* ♿ **Accessibility** — skip link, landmarks, `aria-expanded` accordions, `role=checkbox` checklist, live-region result counts, keyboard shortcuts (`/` to search, `Esc` to close)

## 🛠️ Tech Stack

* 🐍 Python 3.11+ + 🌐 Flask 3 + 🎨 HTML/CSS/vanilla JS + 📄 JSON
* No database — all content lives in `data/guides.json` (loaded **once** into memory at startup + prebuilt search index, so requests never touch disk).

## 🚀 Run locally

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
python app.py
# production-style (no debug):
# FLASK_DEBUG=0 python app.py
```

Then open `http://127.0.0.1:5000`.

Health check: `GET /health` (alias `/ping`) → `{"status": "ok", "app": "DaneshRah"}`.

## 📁 Project Structure

```text
daneshrah/
├── app.py                  # DaneshRah Flask app: cached data, ranked search, routes, API
├── data/guides.json        # ALL content + per-country meta + last_updated (edit only this to add a country)
├── templates/
│   ├── base.html           # shared layout, nav, footer, DaneshRah brand, skip-link
│   ├── index.html          # hero + search + stats + country grid + last_updated
│   ├── country.html        # category cards + essentials + last_updated + related
│   ├── guide.html          # TOC + accordion (ARIA) + progress + print
│   ├── search.html         # ranked results + matched-in badges + friendly empty state
│   ├── checklist.html      # interactive arrival checklist (localStorage)
│   ├── emergency.html      # emergency/essentials table + filter + last check
│   ├── 404.html
│   └── 500.html
├── static/
│   ├── style.css           # design system + dark mode + a11y (skip-link, badges, focus)
│   └── app.js              # theme, normalized filter, reveal, checklist, favorites, TOC
├── requirements.txt        # Flask==3.0.3, gunicorn==22.0.0
├── render.yaml             # Render deploy (service: daneshrah, healthCheck: /health)
└── README.md
```

## ➕ How to add a new country (no code needed)

`data/guides.json` is the single source of truth. Copy any country block and fill in `meta` + `last_updated`:

```json
{
  "germany": {
    "name": "آلمان",
    "flag": "🇩🇪",
    "blurb": "چرا این راهنما…",
    "meta": {
      "capital": "برلین",
      "currency": "یورو (€)",
      "language": "آلمانی",
      "emergency": "۱۱۲",
      "region": "europe",
      "region_label": "اروپا"
    },
    "last_updated": "2026-10-19",
    "categories": {
      "shopping": {
        "title": "خرید و زندگی روزمره",
        "items": [
          {
            "title": "سوپرمارکت‌ها",
            "content": "توضیح با لینک [Aldi](https://www.aldi.de) …"
          }
        ]
      },
      "housing": { "title": "مسکن", "items": [] },
      "admin": { "title": "اقامت و امور اداری", "items": [] },
      "work": { "title": "کار دانشجویی", "items": [] }
    },
    "sources": [
      {
        "title": "DAAD — کار دانشجویی",
        "url": "https://www.daad.de/en/studying-in-germany/living-in-germany/working-in-germany/",
        "cat": "work"
      }
    ]
  }
}
```

Rules:

* `meta.region` should reuse one of `europe`, `north_america`, `asia`, `oceania` when possible (anything else shows under «سایر» automatically).
* `last_updated` is Gregorian `YYYY-MM-DD` and renders as e.g. «۱۹ اکتبر ۲۰۲۶».
* Item `content` supports `[label](https://…)` links — they open in a new tab safely.
* `sources` is an optional per-country list of `{title, url, cat}` — it renders as «منابع رسمی» on the country page; `cat` is one of `shopping`/`housing`/`admin`/`work`.
* Categories currently supported: `shopping`, `housing`, `admin`, `work` (labels/icons via `CATEGORY_META` in `app.py`; `general.categories.arrival` powers `/checklist`).

## 🔎 How search works

`normalize_fa()` unifies text before comparing:

* `ي/ك/ى/ة` → `ی/ک/ی/ه`, `آ/أ/إ` → `ا`, `ؤ` → `و`
* half-space (ZWNJ) and zero-width chars → space, tashkeel/tatweel removed
* Persian/Arabic digits → ASCII, lowercase, whitespace collapsed

Ranking per item: **title (+10) > country name (+6) > category (+4) > content (+2)**, plus exact-phrase bonus (title +15) and all-tokens bonus. Multi-word queries prefer items matching **all** tokens (AND), falling back to partial matches (OR) when needed. Snippets are 150-char windows around the first hit with word-boundary ellipsis.

Client-side country/emergency filters use the same normalization, so «سیم‌کارت», «سیم کارت» and «سیمکارت» all match.

## ⚡ Performance

* `data/guides.json` is read **once** at import (`get_guides()`), kept in RAM, and only re-read when its mtime changes (handy in dev).
* A normalized **search index** is prebuilt once (`get_search_index()`) — per-query work is just scoring, no disk I/O.
* Security headers (`nosniff`, `DENY` framing) + no `debug=True` in production (`FLASK_DEBUG=1` only for local dev).

## ♿ Accessibility & UX

* Skip-to-content link, `<main id="main">`, labeled landmarks and breadcrumbs.
* Guide accordion uses `role=button` + `aria-expanded`/`aria-controls`; checklist uses `role=checkbox` + `aria-checked` and a real `role=progressbar`.
* Filter/result counts use `role="status"` + `aria-live="polite"`; TOC marks current section with `aria-current`.
* Keyboard: `/` focuses search, `Enter`/`Space` toggles accordion/checklist, `Esc` closes menu, `↑` button scrolls top.
* Empty states explain what to try next (shorter word, drop half-space) instead of a dead end.

## 🚢 Deploy (Render)

`render.yaml` defines service **`daneshrah`** (`gunicorn app:app`, health check `/health`). `app.py` also self-pings `$RENDER_EXTERNAL_URL/health` when set, and `.github/workflows/keep-alive.yml` pings every 10 min as a backup — set repo secret `RENDER_URL=https://daneshrah.onrender.com`.

## 🎯 Goal

One accessible place for the small-but-critical questions: where to buy a SIM, how to open a bank account, how deposits work, how to register your address — written plainly, without hype, and with a link to the official source so you can double-check.

## 👨‍💻 Author

**Matin Isapoor** — [GitHub](https://github.com/MatinIsapoor)

---

⭐ If DaneshRah helped you, forward it to the next person — that's enough for us.

---

## 🇮🇷 راهنمای فارسی

**دانش‌راه (DaneshRah)** یک وب‌اپ Flask برای راهنمای زندگی دانشجویی ایرانی‌ها در کشورهای مختلف است: خرید، مسکن، بانک، سیم‌کارت و چک‌لیست روزهای اول.

* اجرای محلی: دستورات بالا (بعدش `http://127.0.0.1:5000`)
* افزودن کشور/مطلب جدید: فقط `data/guides.json` را ویرایش کن — نیازی به تغییر کد نیست. هر کشور `meta` (پایتخت، واحد پول، زبان، اضطراری، منطقه)، `last_updated` (مثل `2026-10-19`) و فهرست اختیاری `sources` (`{title, url, cat}`) دارد که در صفحه‌ی کشور به‌عنوان «منابع رسمی» نمایش داده می‌شود.
* جست‌وجو نیم‌فاصله و ی/ک را خودش درست می‌کند؛ ترتیب نتایج: تیتر، بعد نام کشور، بعد متن.
* صفحات: `/search` جست‌وجو، `/checklist` چک‌لیست تعاملی، `/emergency` شماره‌های اضطراری.

پیشنهادها و مشارکت‌ها خوش‌آمدند! 🙌
