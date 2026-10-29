# DaneshRah | دانش‌راه

DaneshRah is an independent, Persian-language guide for the practical parts of student life abroad: SIM cards, banking, deposits, housing, residence paperwork, health insurance, student work, and the first days after arrival.

The site contains **42 country guides plus one general arrival guide**, **746 guide items**, and **148 listed sources**. It is a Flask app with a JSON content file and a small vanilla-JavaScript front end.

> من متینم و دانش‌راه را ساختم تا جواب سؤال‌های ریزِ شروع زندگی در کشور جدید — از ودیعه و سیم‌کارت تا بیمه و اقامت — یک‌جا و همراه با لینک منبع رسمی در دسترس باشد. اطلاعات کشورها در فایل JSON نگهداری می‌شود. اگر جایی اشتباه یا قدیمی بود، از طریق GitHub بگو تا اصلاح شود.
> **Deployment status (2026-10-30):** the configured public URL, `https://daneshrah.onrender.com`, returned **HTTP 503 — “Service Suspended”** during this audit. The code is tested locally, but the live deployment was not available and production startup was not verified. See [Deployment](#deployment).

## What is included

- Country discovery by region, with search and a “favorites” filter.
- Country pages with essentials, category counts, official-source lists, related countries, and honest data-freshness labels.
- Guide pages with a table of contents, expandable items, deep links (`#item-N`), copy buttons, reading progress, and print styles.
- Persian search with normalization for Arabic/Persian variants, half-spaces, and digits; results link directly to the matching guide item.
- An 11-step interactive arrival checklist stored in `localStorage`, with progress and reset.
- An emergency/essentials directory for all 42 countries with client-side filtering.
- Light and dark themes, reduced-motion support, keyboard navigation, skip link, visible focus states, and mobile layouts tested down to 320 px.
- An About page covering the project, data policy, limitations, and a single creator credit.

## Stack

| Layer | Choice |
| --- | --- |
| Server | Python, Flask 3.1.3 |
| Content | `data/guides.json` (no database) |
| Front end | Server-rendered Jinja templates, vanilla JavaScript, CSS design system |
| Typography | Vazirmatn for body text, Markazi Text for display headings (Google Fonts) |
| Flags | FlagCDN images with a text/emoji fallback |
| Production server | Gunicorn 26.2.0 (Unix-only), configured for Render |
| Tests | Standard-library `unittest`, Node’s built-in test runner, `guide_validation.py` |

## Run locally

Recommended: Python 3.11 or newer (Render is configured for Python 3.11.9). The audit machine used Python 3.14.7.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`. On macOS/Linux, activate with `source .venv/bin/activate`.

`python app.py` starts Flask’s development server only. It is not the production command.

## Tests and validation

Run these from the project root:

```powershell
python -m unittest discover -s tests -t .
node --test tests/js_utils.test.js
python guide_validation.py
```

Final local results on 2026-10-30:

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -t .` | **95 tests, OK** with the system Flask 3.0.3 |
| Same command in a clean venv with **Flask 3.1.3** | **95 tests, OK** |
| `node --test tests/js_utils.test.js` | **7 passed, 0 failed** |
| `python guide_validation.py` | **0 errors, 0 warnings** |

The Python suite covers routes, status codes, security headers/CSP, canonical and robots metadata, search behavior, API limits, data invariants, and selected HTML/accessibility regressions. The Node suite covers the shared Persian-normalization and clipboard helpers.

Browser checks were also run against the local server with headless Chrome 155.0.8059.85:

- Desktop and mobile layouts at 320, 360, 390, 768, 1024, 1280, and 1440 px.
- Mobile navigation and search panel.
- Country filtering, search anchors, guide accordion/deep links/copy, checklist persistence/reset, emergency filtering, theme persistence, and CSP console errors.
- An axe-core 4.10.2 scan reported **0 violations** across ten page/viewport checks, including mobile, desktop, and dark-theme pages. A few “incomplete” results remained because axe could not determine contrast/overlap around pseudo-elements; those were not confirmed failures.

These are automated and headless-browser checks, not a substitute for a manual WCAG audit, screen-reader testing, or real-device testing.

## Data model and freshness

`data/guides.json` is the single source of truth. Each country entry contains:

- `name`, `flag`, `blurb`, `meta` (capital, currency, language, emergency number, region), and `last_updated`.
- `categories` for `shopping`, `housing`, `admin`, and `work`; each category has a title and a list of items.
- An optional `sources` list of `{title, url, cat}` entries.

The `general` entry supplies the `arrival` checklist; it is not a country and has no sources of its own.

`last_updated` is a **file-level edit stamp**, not proof that every fact on that country page was rechecked that day. The UI labels it «آخرین ویرایش داده» and the About/guide pages explain the limitation.

Current status:

- **France** and **Australia** are stamped `2026-10-23` after targeted review.
- The other **41 entries** (40 countries plus `general`) share `2026-10-19`; they were **not** individually line-by-line fact-checked in this audit.
- A cleanup removed unsupported or misattributed inline citations; no replacement URLs were invented. The remaining source list is the place to start checking a claim.

Targeted checks completed during the audit:

| Topic | Checked fact | Official source |
| --- | --- | --- |
| Australia minimum wage | A$26.44 per hour from 1 July 2026 | [Fair Work Ombudsman](https://www.fairwork.gov.au/pay-and-wages/minimum-wages) |
| Australia student work limit | 48 hours per fortnight during the term | [Home Affairs — Student visa 500](https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500) |
| France CROUS meal | €1 meal from 4 May 2026 for eligible students with an active Izly account | [etudiant.gouv.fr](https://www.etudiant.gouv.fr/fr/comment-beneficier-du-repas-crous-1-eu-3123) |
| France APL | Eligibility rules changed from 1 July 2026; check before signing a lease | [Service-Public — APL](https://www.service-public.gouv.fr/particuliers/vosdroits/F1563) |
| France SMIC | €12.31 gross per hour from 1 June 2026 | [Service-Public — SMIC](https://www.service-public.gouv.fr/particuliers/vosdroits/F2300) |

Rates, eligibility rules, and visa conditions change. The inline official links in each guide are the primary source trail; this README is not legal, financial, or immigration advice.

After editing the data file, run:

```powershell
python guide_validation.py
```

The validator checks required fields, unsafe URLs, duplicate item titles, malformed Markdown links, and impossible dates. It exits with code 1 when structural errors are present, so it can be used in CI.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Homepage and country discovery |
| `/country/<code>` | Country overview |
| `/country/<code>/<category>` | Category guide with item anchors |
| `/search?q=...` | Ranked Persian search |
| `/checklist` | Interactive arrival checklist |
| `/emergency` | Emergency and essentials table |
| `/about` | Project background, data policy, limitations, creator credit |
| `/api/countries` | Country metadata JSON |
| `/api/search?q=...&limit=...` | Search JSON; query capped at 200 characters, limit at 50 |
| `/health`, `/ping` | Liveness/data check for Render and the keep-alive pinger |
| `/robots.txt`, `/sitemap.xml` | Crawler policy and sitemap |

`/search` and `/country/general*` return `X-Robots-Tag: noindex, follow` and matching meta robots tags. `/search` is deliberately excluded from the sitemap. The generic arrival text is available for the checklist, but should not compete with country guides in search results.

## Search

`normalize_fa()` unifies Persian/Arabic characters, half-spaces, zero-width characters, tashkeel, tatweel, and Persian/Arabic digits before scoring. Ranking favors title matches, then country name, category, and content, with exact-phrase and all-token bonuses. Multi-word queries prefer items matching all tokens and fall back to partial matches.

The search index is built once in memory from the validated JSON file. Search results deep-link to `/country/<code>/<category>#item-N`; the target item is opened and highlighted by the front end.

## Design and accessibility

The visual system uses a warm paper background, deep ink/teal, brick and gold accents, fine rules, flat surfaces, and restrained motion. Vazirmatn and Markazi Text provide Persian body and display typography. Components share tokens for spacing, color, focus, borders, and states.

The redesign includes:

- Reusable page, card, button, pill, form, callout, table, and navigation patterns.
- Responsive country grid, mobile menu, mobile search panel, and 320 px-safe filter controls.
- Light/dark themes with a no-flash inline bootstrap; the chosen theme persists.
- `prefers-reduced-motion` handling and print styles for guide pages.
- Skip link, one `main` landmark, labeled navigation and forms, visible labels for checklist inputs, `aria-current` for active navigation, `aria-live` status messages, and keyboard-operable accordions.
- Callouts use non-landmark containers where a nested `aside` would be invalid, and templates contain no inline `style` attributes. The only runtime inline style is the reading-progress width written by JavaScript; it does not require `style-src 'unsafe-inline'`.

The automated axe scan is evidence of baseline hygiene, not a claim of full WCAG 2.2 AA conformance. A manual audit and assistive-technology testing are still recommended.

## Security and SEO

- Per-request CSP nonce for the single inline theme bootstrap; scripts are same-origin plus the nonce.
- `style-src 'self' https://fonts.googleapis.com`; no `unsafe-inline` for styles.
- Security headers include `nosniff`, frame denial, `Referrer-Policy`, `Permissions-Policy`, CORP/COOP, and HSTS on HTTPS only.
- Canonical URLs, Open Graph/Twitter tags, JSON-LD, `/robots.txt`, and `/sitemap.xml`.
- Canonical origins come from `PUBLIC_BASE_URL`, then `RENDER_EXTERNAL_URL`, then the configured default. The request `Host` header is never trusted for canonical URLs.
- Search input is truncated to 200 characters; API limits are clamped; request bodies are capped at 1 MiB; errors return a styled generic page with the correct status code.
- Request IDs are accepted only when they match a safe pattern, otherwise generated server-side.
- The app has no accounts, sessions, or user-submitted persistence. Theme, checklist, and favorites live in browser `localStorage`.

## Deployment

`render.yaml` defines the Render web service, the build command, the health check (`/health`), and the start command:

```text
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4
```

Useful environment variables:

| Variable | Purpose |
| --- | --- |
| `PUBLIC_BASE_URL` | Preferred public origin for canonical/OG/sitemap URLs; set this when using a custom domain |
| `RENDER_EXTERNAL_URL` | Render-provided origin; used automatically when `PUBLIC_BASE_URL` is unset |
| `PORT` | Local development port; Render supplies it in production |
| `KEEP_ALIVE_URL` | Optional URL for the in-process keep-alive thread |
| `KEEP_ALIVE_INTERVAL` | Keep-alive interval in seconds (default 600, minimum 60) |
| `FLASK_DEBUG` | `0` for production; `1` only for local development |

Important verification limits:

- **Gunicorn was installed in the clean venv but could not be started on Windows.** It fails with `ModuleNotFoundError: No module named 'fcntl'`. The Render start command therefore remains unexercised.
- The public Render URL returned **503 Service Suspended** on 2026-10-30. Resume/redeploy the service, then verify `/health`, security headers, canonical URLs, and the sitemap in the actual environment.
- The optional GitHub Actions keep-alive workflow requires the `RENDER_URL` repository secret; it was not verified against the suspended service.
- Google Fonts and FlagCDN are external dependencies. Self-host fonts and flags if you need a fully offline or privacy-minimized deployment.

Before calling a deployment production-ready, verify at minimum:

1. `pip install -r requirements.txt` on the target Python version.
2. Gunicorn starts and `/health` returns 200 with the expected counts.
3. HTTPS/HSTS, CSP, canonical URLs, and `robots.txt`/`sitemap.xml` in the deployed environment.
4. The real domain is set via `PUBLIC_BASE_URL`.
5. The targeted facts above and any recently changed rules are rechecked against official sources.

## Known limitations

- The 42-country dataset is broad, but only France and Australia received targeted fact review in this audit; most entries still need country-by-country verification.
- Search is lexical, not semantic; it is designed for short Persian queries and may miss paraphrases.
- No database, authentication, user accounts, or server-side personal data storage.
- Browser evidence is from headless Chrome only; Safari/Firefox and real mobile devices were not tested.
- Automated accessibility checks found no axe violations, but manual WCAG and screen-reader testing were not completed.
- Production deployment, Gunicorn startup, and the live service were not verified; the public URL was suspended during the audit.

## Project background and credit

The `/about` page documents the project’s origin, data policy, and limitations, and contains the single genuine creator credit. The repository is [MatinIsapoor/DaneshRah](https://github.com/MatinIsapoor/DaneshRah).

---

## خلاصه فارسی

دانش‌راه یک راهنمای مستقل فارسی برای زندگی دانشجویی در خارج از کشور است: ۴۲ کشور به‌همراه راهنمای عمومی ورود، ۷۴۶ نکته و ۱۴۸ منبع. محتوا در `data/guides.json` نگهداری می‌شود و بدون پایگاه داده اجرا می‌شود.

اجرای محلی:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

* افزودن کشور/مطلب جدید: فقط `data/guides.json` را ویرایش کن — نیازی به تغییر کد نیست. هر کشور `meta` (پایتخت، واحد پول، زبان، اضطراری، منطقه)، `last_updated` (مثل `2026-10-19`) و فهرست اختیاری `sources` (`{title, url, cat}`) دارد که در صفحه‌ی کشور به‌عنوان «منابع رسمی» نمایش داده می‌شود.
* جست‌وجو نیم‌فاصله و ی/ک را خودش درست می‌کند؛ ترتیب نتایج: تیتر، بعد نام کشور، بعد متن.
* صفحات: `/search` جست‌وجو، `/checklist` چک‌لیست تعاملی، `/emergency` شماره‌های اضطراری.
* تست‌ها: `python -m unittest discover -s tests -t .` — بررسی مسیرها، جست‌وجو، امنیت، HTML و داده.
* اعتبارسنجی داده: `python guide_validation.py` — اگر فیلدی کم، لینک ناامن، تاریخ غلط یا لینک مارک‌داون خراب باشد، خطا می‌دهد.
* ارتباط: تلگرام [@caspianix](https://t.me/caspianix) — توییتر [@persianix](https://x.com/persianix) — گیت‌هاب [MatinIsapoor](https://github.com/MatinIsapoor).

```powershell
python -m unittest discover -s tests -t .
node --test tests/js_utils.test.js
python guide_validation.py
```

نتیجه‌ی نهایی: ۹۵ تست پایتون، ۷ تست Node و اعتبارسنجی داده با ۰ خطا و ۰ هشدار. تاریخ «آخرین ویرایش داده» مهر فایل است و تضمین بازبینی خط‌به‌خط همه‌ی کشورها نیست. تنها فرانسه و استرالیا در این بازبینی بررسی هدفمند شدند. اجرای production با Gunicorn روی ویندوز آزمون نشد و سرویس عمومی Render در زمان بازبینی با خطای ۵۰۳ (تعلیق سرویس) در دسترس نبود.
